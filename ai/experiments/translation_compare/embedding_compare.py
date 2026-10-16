"""자막 검색(d)·설명문 검색(e)의 임베딩 모델 비교 (dev에서만).

    python ai/experiments/translation_compare/embedding_compare.py --results ~/scenefinder_eval/results_v2 \
        --queries 라벨.json --subset dev --out ~/scenefinder_eval/embedding_compare/results.json
    python ai/experiments/translation_compare/embedding_compare.py --report ~/scenefinder_eval/embedding_compare/results.json

- 자막·설명문·영상 길이는 --results 폴더(run.py·captions.py 결과)의 것을 그대로 씁니다. 바뀌는 것은 임베딩 모델뿐입니다.
- 검색 방식은 서비스와 같습니다: 연속 1~3문장 묶음 창을 만들어 질의와 코사인 유사도로 순위. (d)는 서비스 구간 보정
  (시작 2초 앞당김, 최소 6초), (e)는 1위 창 구간 그대로(M0).
- 모델마다 새 프로세스에서 돌려 GPU 메모리(torch 최대 할당량)와 시간을 따로 잽니다.
  색인 시간 = 영상의 모든 창을 임베딩하는 시간(영상마다 한 번), 검색 시간 = 질의 1개를 임베딩하고 순위를 매기는 시간.
- multilingual-e5는 모델 설명대로 질의에 "query: ", 문장에 "passage: "를 붙입니다.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import query_set  # noqa: E402
import summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MODELS = {
    "minilm": {"label": "fine-tuned MiniLM (서비스 현재)", "name": "SCENEFINDER_MINILM_MODEL_PATH"},
    "bge-m3": {"label": "BAAI/bge-m3", "name": "BAAI/bge-m3"},
    "e5-large": {"label": "intfloat/multilingual-e5-large", "name": "intfloat/multilingual-e5-large",
                 "query_prefix": "query: ", "doc_prefix": "passage: "},
}
PAD_BEFORE, MIN_LEN = 2.0, 6.0   # 서비스 자막 구간 보정 (run.py와 같은 기본값)


def windows(items):
    out = []
    for size in (1, 2, 3):
        for i in range(len(items) - size + 1):
            g = items[i:i + size]
            out.append({"start": float(g[0]["start_time"]), "end": float(g[-1]["end_time"]),
                        "text": " ".join(s["text"] for s in g)})
    return out


def widen(seg):
    start = max(0.0, seg[0] - PAD_BEFORE)
    return (start, max(seg[1], start + MIN_LEN))


def worker(model_key, args):
    import torch
    from dotenv import load_dotenv

    load_dotenv(ROOT / "backend" / ".env")
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    spec = MODELS[model_key]
    torch.cuda.reset_peak_memory_stats()
    t = time.perf_counter()
    if model_key == "minilm":
        from ai.features.fusion_search import get_semantic_model
        model = get_semantic_model(model_type="finetuned")
    else:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(spec["name"], device="cuda")
    torch.cuda.synchronize()
    load_sec = time.perf_counter() - t
    mem_load = torch.cuda.max_memory_allocated() / 2**20
    qp, dp = spec.get("query_prefix", ""), spec.get("doc_prefix", "")

    def enc(texts):
        return model.encode(texts, convert_to_tensor=True, normalize_embeddings=True, batch_size=64)

    out = Path(args.results).expanduser()
    qs = query_set.load(args.queries, args.subset)
    caps = json.loads((out / "captions_qwen_incl.json").read_text(encoding="utf-8"))["videos"]
    enc(["워밍업"])

    index, index_sec = {}, {}
    for key in qs.video_keys:
        subs = json.loads((out / f"bench_{key}_subtitles.json").read_text(encoding="utf-8"))["segments"]
        for kind, items in (("d", subs), ("e", caps[key])):
            ws = windows(items)
            torch.cuda.synchronize(); t = time.perf_counter()
            emb = enc([dp + w["text"] for w in ws]) if ws else None
            torch.cuda.synchronize()
            index[(key, kind)] = (ws, emb)
            index_sec[f"{key}/{kind}"] = {"windows": len(ws), "sec": time.perf_counter() - t}

    rows, query_secs = [], []
    for num, key, typ, ko, gts in qs.queries:
        row = {"num": num, "video": key, "type": typ, "query": ko, "gt": gts, **qs.info[num]}
        for kind in ("d", "e"):
            ws, emb = index[(key, kind)]
            if emb is None:
                row[kind] = {"seg": None, "iou": 0.0, "top3": []}
                continue
            torch.cuda.synchronize(); t = time.perf_counter()
            q = enc([qp + ko])[0]
            scores = (emb @ q).float()
            order = torch.argsort(scores, descending=True)[:100].tolist()
            torch.cuda.synchronize(); query_secs.append(time.perf_counter() - t)
            spans = [(ws[i]["start"], ws[i]["end"]) for i in order]
            if kind == "d":
                spans = [widen(s) for s in spans]
            row[kind] = {"seg": spans[0], "iou": summary.best_iou(spans[0], gts), "score": float(scores[order[0]]),
                         "text": ws[order[0]]["text"], "top3": summary.nms_top(spans)}
        rows.append(row)
    return {"model": model_key, "label": spec["label"], "load_sec": load_sec, "gpu_mib_after_load": mem_load,
            "gpu_mib_peak": torch.cuda.max_memory_allocated() / 2**20, "index_sec": index_sec,
            "query_sec_mean": sum(query_secs) / len(query_secs), "query_sec_p95": sorted(query_secs)[int(len(query_secs) * 0.95)],
            "rows": rows}


def report(path, output):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    models = data["models"]
    # s_kind(말 내용 등)는 결과 행에 없으므로 실험에 쓴 라벨 파일에서 붙임
    labels = json.loads(Path(data["queries"]).expanduser().read_text(encoding="utf-8"))
    kinds = {q["num"]: q.get("s_kind") for q in labels["queries"]}
    for m in models:
        for r in m["rows"]:
            r["s_kind"] = kinds.get(r["num"])
    L = ["# 임베딩 모델 비교: 자막 검색(d)·설명문 검색(e) (dev)", "",
         f"평가셋 v2의 **dev 영상 {len({r['video'] for r in models[0]['rows']})}개**에서 자막 검색(d)과 설명문 검색(e)의 임베딩 모델만 바꿔 비교했습니다. "
         "자막(Whisper small)·설명문(Qwen3-VL-4B, 1장씩 처리)·검색 방식(연속 1~3문장 창, 코사인 유사도, 서비스 구간 보정)은 "
         "[eval_v2.md](eval_v2.md)와 같고 임베딩 모델만 다릅니다. test 영상은 쓰지 않았습니다.", ""]
    groups = [("S", "검수된 S"), ("V", "검수된 V"), ("speech", "말 내용 S (AI 초안, 미검수)")]

    def pick(rows, g):
        if g == "speech":
            return [r for r in rows if r.get("s_kind") == "말 내용"]
        return [r for r in rows if r["type"] == g and r.get("source") != "ai_draft"]

    def agg(rows, kind):
        fn = summary.by_key(kind)
        vals = [fn(r) for r in rows]
        n = len(vals)
        return n, sum(v[1] for v in vals), sum(v[2] for v in vals), sum(v[3] for v in vals), sum(v[0] for v in vals) / n

    for kind, title in (("d", "자막 검색 (d)"), ("e", "설명문 검색 (e)")):
        L += [f"## {title}", "", "각 칸: IoU ≥ 0.3 / IoU ≥ 0.5 / R@3 (개수, 평균 IoU)", "",
              "| 모델 | " + " | ".join(f"{label} (n={len(pick(models[0]['rows'], g))})" for g, label in groups) + " |",
              "|---|" + "---|" * len(groups)]
        for m in models:
            cells = []
            for g, _ in groups:
                rs = pick(m["rows"], g)
                if not rs:
                    cells.append("–")
                    continue
                n, h3, h5, r3, miou = agg(rs, kind)
                cells.append(f"{h3:.0f} / {h5:.0f} / {r3:.0f} ({miou:.2f})")
            L.append(f"| {m['label']} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## 검색 시간과 GPU 메모리", "",
          "| 모델 | 모델 로딩 | 색인 (dev 영상 전체, 자막+설명문) | 질의 1개 검색 (평균 / 95%) | GPU 메모리 (로딩 후 / 최대) |",
          "|---|---|---|---|---|"]
    for m in models:
        idx = sum(v["sec"] for v in m["index_sec"].values())
        nwin = sum(v["windows"] for v in m["index_sec"].values())
        load = (f"{m['load_sec_cached']:.1f}초 (첫 실행 {m['load_sec']:.0f}초, 다운로드 포함)" if "load_sec_cached" in m
                else f"{m['load_sec']:.1f}초")
        L.append(f"| {m['label']} | {load} | {idx:.1f}초 (창 {nwin:,}개) | "
                 f"{m['query_sec_mean'] * 1000:.0f} / {m['query_sec_p95'] * 1000:.0f} ms | "
                 f"{m['gpu_mib_after_load']:,.0f} / {m['gpu_mib_peak']:,.0f} MiB |")
    L += ["", "- GPU 메모리는 torch가 할당한 최댓값(`torch.cuda.max_memory_allocated`)입니다. 색인할 때 64개씩 묶어 임베딩합니다.",
          "- 검색 시간은 질의 임베딩 + 영상 하나의 창 전체와 유사도 계산 + 정렬입니다(색인은 미리 만들어 둔 상태).",
          f"- 환경: {data.get('gpu', '')}", ""]
    L += ["## 해석", "", data.get("interpretation", "(결과를 보고 작성)"), ""]
    L += ["## 재현 방법", "", "    python ai/experiments/translation_compare/embedding_compare.py --results ~/scenefinder_eval/results_v2 \\",
          "        --queries ~/scenefinder_eval/labels_draft.json --subset dev --out ~/scenefinder_eval/embedding_compare/results.json",
          "    python ai/experiments/translation_compare/embedding_compare.py --report ~/scenefinder_eval/embedding_compare/results.json", "",
          "- bge-m3·multilingual-e5-large는 처음 실행할 때 Hugging Face에서 내려받습니다(각각 약 2GB).",
          "- fine-tuned MiniLM 결과는 run.py의 (d)·(e) 결과와 같은지 실행할 때 확인합니다(`minilm_matches_run`).", ""]
    Path(output).write_text("\n".join(L), encoding="utf-8")
    print("작성:", output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results")
    parser.add_argument("--queries")
    parser.add_argument("--subset", default="dev", choices=query_set.SUBSETS)
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--out")
    parser.add_argument("--report", help="결과 JSON으로 문서 생성")
    parser.add_argument("--output", default=str(ROOT / "docs/experiments/embedding_compare.md"))
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.report:
        report(args.report, args.output)
        return
    if args.worker:
        Path(args.worker_out).write_text(json.dumps(worker(args.worker, args), ensure_ascii=False))
        return
    if not (args.results and args.queries and args.out):
        parser.error("--results, --queries, --out이 필요합니다")
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    data = {"results": str(args.results), "queries": str(args.queries), "subset": args.subset, "gpu": gpu, "models": []}
    for m in args.models.split(","):
        tmp = out.with_name(f".{m}.json")
        print(f"== {time.strftime('%H:%M:%S')} {m}", flush=True)
        subprocess.run([sys.executable, __file__, "--results", args.results, "--queries", args.queries, "--subset", args.subset,
                        "--worker", m, "--worker-out", str(tmp)], check=True)
        data["models"].append(json.loads(tmp.read_text()))
        tmp.unlink()
    # 확인: MiniLM 결과가 run.py 결과와 같은지 (같은 질의 번호의 1위 구간)
    run_rows = {r["num"]: r for r in json.loads((Path(args.results).expanduser() / "results.json").read_text())["rows"]}
    mini = next((m for m in data["models"] if m["model"] == "minilm"), None)
    if mini:
        diff = 0
        for r in mini["rows"]:
            rr = run_rows.get(r["num"])
            if not rr or rr["query"] != r["query"]:
                continue
            for kind, rk in (("d", "d"), ("e", "e_qwen_incl")):
                a, b = r[kind].get("seg"), (rr.get(rk) or {}).get("seg")
                if (a is None) != (b is None) or (a and any(abs(x - y) > 1e-6 for x, y in zip(a, b))):
                    diff += 1
        data["minilm_matches_run"] = diff == 0
        data["minilm_mismatches"] = diff
        print("MiniLM과 run.py 1위 구간 불일치:", diff)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", out)


if __name__ == "__main__":
    main()
