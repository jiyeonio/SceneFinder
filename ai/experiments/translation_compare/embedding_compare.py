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


NOISE = 3   # 설명문을 다시 만드는 것만으로 dev 47개 중 이 정도 움직임 (caption_batch_compare.md)


def annotate_kinds(models, queries_path):
    """S 질의 종류(말 내용/화면 묘사): 라벨의 s_kind, 없으면 eval_v2_s_query_kinds.tsv (질의 문장만 보고 정한 분류)."""
    import csv
    labels = json.loads(Path(queries_path).expanduser().read_text(encoding="utf-8"))
    tsv = ROOT / "docs/experiments/eval_v2_s_query_kinds.tsv"
    kinds = {}
    if tsv.exists():
        with open(tsv, encoding="utf-8") as f:
            kinds = {int(r["num"]): r["kind"] for r in csv.DictReader(f, delimiter="\t")}
    for q in labels["queries"]:
        if q.get("s_kind"):
            kinds[q["num"]] = q["s_kind"]
    for m in models:
        for r in m["rows"]:
            r["s_kind"] = kinds.get(r["num"]) if r["type"] == "S" else None


def report(path, output, test_path=None):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    models = data["models"]
    annotate_kinds(models, data["queries"])
    res_meta = json.loads((Path(data["results"]).expanduser() / "results.json").read_text(encoding="utf-8"))["meta"]
    cap_meta = json.loads((Path(data["results"]).expanduser() / "captions_qwen_incl.json").read_text(encoding="utf-8"))["meta"]
    bs = cap_meta.get("result_batch_size", 1)
    groups = [("speech", "S 말 내용"), ("visual", "S 화면 묘사"), ("V", "V")]

    def pick(rows, g):
        if g == "speech":
            return [r for r in rows if r["type"] == "S" and r.get("s_kind") == "말 내용"]
        if g == "visual":
            return [r for r in rows if r["type"] == "S" and r.get("s_kind") != "말 내용"]
        return [r for r in rows if r["type"] == "V"]

    def counts(rows, kind):
        fn = summary.by_key(kind)
        v = [fn(r) for r in rows]
        return [sum(x[1] for x in v), sum(x[2] for x in v), sum(x[3] for x in v)], sum(x[0] for x in v) / max(len(v), 1)

    n_videos = len({r["video"] for r in models[0]["rows"]})
    L = ["# 임베딩 모델 비교: 자막 검색(d)·설명문 검색(e) (dev)", "",
         f"평가셋 v2의 **dev 영상 {n_videos}개, 질의 {len(models[0]['rows'])}개**에서 자막 검색(d)과 설명문 검색(e)의 임베딩 모델만 바꿔 비교했습니다. "
         f"자막은 Whisper `{res_meta['whisper']}`, 설명문은 Qwen3-VL-4B "
         f"{'1장씩' if bs == 1 else f'{bs}장 묶음'} 처리 결과를 그대로 쓰고, 검색 방식(연속 1~3문장 창, 코사인 유사도, 자막은 서비스 구간 보정)도 "
         "[eval_v2.md](eval_v2.md)와 같습니다. test 영상은 쓰지 않았습니다.", "",
         "질의는 모두 사람이 검수한 것(human_reviewed)입니다. S는 말 내용을 찾는 질의(소리만 들어도 찾을 수 있음)와 화면을 묘사하는 질의로 나눴습니다"
         "([분류 기준](eval_v2.md#s-질의-편향-점검-말-내용-vs-화면-묘사)).", "",
         f"**잡음 수준:** 같은 조건에서 설명문을 다시 만드는 것만으로 dev 47개 중 IoU ≥ 0.3·R@3이 최대 {NOISE}개 움직였습니다"
         "([caption_batch_compare.md](caption_batch_compare.md)). 이 비교는 같은 설명문 파일을 쓰므로 그 잡음은 없지만, 질의 수가 적어 "
         f"**MiniLM 대비 ±{NOISE}개 이내의 차이는 의미 있게 보지 않습니다.** 표에서 {NOISE}개를 넘게 차이 나는 칸만 ▲(많음)/▼(적음)으로 표시했습니다.", ""]
    def table(models, kind, title, level):
        out = [f"{level} {title}", "", "각 칸: IoU ≥ 0.3 / IoU ≥ 0.5 / R@3 (개수, 괄호는 평균 IoU)", "",
               "| 모델 | " + " | ".join(f"{label} (n={len(pick(models[0]['rows'], g))})" for g, label in groups) + " |",
               "|---|" + "---|" * len(groups)]
        base = {g: counts(pick(models[0]["rows"], g), kind)[0] for g, _ in groups}
        for m in models:
            cells = []
            for g, _ in groups:
                rs = pick(m["rows"], g)
                if not rs:
                    cells.append("–")
                    continue
                c, miou = counts(rs, kind)
                marks = [("▲" if x - y > NOISE else "▼" if y - x > NOISE else "") for x, y in zip(c, base[g])]
                cells.append(" / ".join(f"{x:.0f}{mk}" for x, mk in zip(c, marks)) + f" ({miou:.2f})")
            out.append(f"| {m['label']} | " + " | ".join(cells) + " |")
        return out + [""]

    def tables(models, level):
        out = []
        for kind, title in (("d", f"자막 검색 (d), Whisper {res_meta['whisper']}"),
                            ("e", f"설명문 검색 (e), {'1장씩' if bs == 1 else f'{bs}장 묶음'} 설명문")):
            out += table(models, kind, title, level)
        return out

    def per_video_sub_encode(models):
        """서비스와 같은 일(영상 하나의 자막 창 전체 임베딩)의 영상별 시간."""
        out = ["| 모델 | " + " | ".join(k.split("/")[0] for k in models[0]["index_sec"] if k.endswith("/d")) + " |",
               "|---|" + "---|" * sum(1 for k in models[0]["index_sec"] if k.endswith("/d"))]
        for m in models:
            out.append(f"| {m['label']} | " + " | ".join(
                f"{v['sec']:.2f}초 (창 {v['windows']})" for k, v in m["index_sec"].items() if k.endswith("/d")) + " |")
        return out

    L += tables(models, "##")
    L += ["## 검색 시간과 GPU 메모리", "",
          "| 모델 | 모델 로딩 | 색인 (**dev 영상 6개 전체**, 자막+설명문) | 질의 1개 검색 (평균 / 95%) | GPU 메모리 (로딩 후 / 최대) |",
          "|---|---|---|---|---|"]
    for m in models:
        idx = sum(v["sec"] for v in m["index_sec"].values())
        nwin = sum(v["windows"] for v in m["index_sec"].values())
        load = (f"{m['load_sec_cached']:.1f}초 (첫 실행 {m['load_sec']:.0f}초, 다운로드 포함)" if "load_sec_cached" in m
                else f"{m['load_sec']:.1f}초")
        L.append(f"| {m['label']} | {load} | {idx:.1f}초 (창 {nwin:,}개) | "
                 f"{m['query_sec_mean'] * 1000:.0f} / {m['query_sec_p95'] * 1000:.0f} ms | "
                 f"{m['gpu_mib_after_load']:,.0f} / {m['gpu_mib_peak']:,.0f} MiB |")
    L += ["", "- GPU 메모리는 torch가 할당한 최댓값(`torch.cuda.max_memory_allocated`)이고, 모델마다 새 프로세스에서 쟀습니다. 색인할 때 64개씩 묶어 임베딩합니다.",
          "- 검색 시간은 질의 임베딩 + 영상 하나의 창 전체와 유사도 계산 + 정렬입니다(색인은 미리 만들어 둔 상태).",
          f"- fine-tuned MiniLM 결과가 run.py 결과와 같은지 확인: {'같음' if data.get('minilm_matches_run') else '다름 ' + str(data.get('minilm_mismatches'))}",
          f"- 환경: {data.get('gpu', '')}", "",
          "### 서비스에서 더해지는 시간", "",
          "위 색인 시간은 dev 영상 6개의 자막 창과 설명문 창을 모두 합친 값입니다. 서비스는 설명문 검색을 쓰지 않고, "
          "**자막 창 임베딩을 분석 때 저장하지 않고 검색할 때마다 영상별로 다시 계산합니다** "
          "(`ai/features/fusion_search.py`의 `get_semantic_subtitle_candidates`). 그래서 모델을 바꾸면 분석 시간이 아니라 "
          "**검색 1번마다, 영상 1개마다** 아래 시간이 더해집니다(질의 임베딩 수 ms 포함 안 함).", ""]
    L += per_video_sub_encode(models)
    L += ["", data.get("service_note", ""), ""]
    L += ["## 해석 (dev)", "", data.get("interpretation", "(결과를 보고 작성)"), ""]
    if test_path:
        tdata = json.loads(Path(test_path).read_text(encoding="utf-8"))
        tmodels = tdata["models"]
        annotate_kinds(tmodels, tdata["queries"])
        L += ["## test 확인 (1회)", "",
              f"dev에서 정한 후보(multilingual-e5-large)를 test 영상 {len({r['video'] for r in tmodels[0]['rows']})}개, "
              f"질의 {len(tmodels[0]['rows'])}개에서 **한 번만** 확인했습니다. 자막·설명문·검색 방식은 dev와 같습니다. "
              f"▲/▼는 dev와 같이 MiniLM 대비 ±{NOISE}개를 넘는 차이입니다.", ""]
        L += tables(tmodels, "###")
        L += ["서비스와 같은 일(영상 하나의 자막 창 임베딩)의 영상별 시간 (test):", ""] + per_video_sub_encode(tmodels) + [""]
        L += [f"- fine-tuned MiniLM 결과가 run.py 결과와 같은지 확인: {'같음' if tdata.get('minilm_matches_run') else '다름'}", ""]
        L += ["### 해석 (test)", "", tdata.get("interpretation", "(결과를 보고 작성)"), ""]
    results_dir = str(data["results"]).replace(str(Path.home()), "~")
    L += ["## 재현 방법", "", f"    python ai/experiments/translation_compare/embedding_compare.py --results {results_dir} \\",
          f"        --queries <라벨 JSON> --subset dev --out <dev 결과 JSON>",
          f"    python ai/experiments/translation_compare/embedding_compare.py --results {results_dir} \\",
          f"        --queries <라벨 JSON> --subset test --models minilm,e5-large --out <test 결과 JSON>   # 최종 확인 1회",
          "    python ai/experiments/translation_compare/embedding_compare.py --report <dev 결과 JSON> --test-report <test 결과 JSON>", "",
          "- bge-m3·multilingual-e5-large는 처음 실행할 때 Hugging Face에서 내려받습니다(각각 약 2GB).", ""]
    Path(output).write_text("\n".join(L), encoding="utf-8")
    print("작성:", output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results")
    parser.add_argument("--queries")
    parser.add_argument("--subset", default="dev", choices=query_set.SUBSETS)
    parser.add_argument("--models", default=",".join(MODELS))
    parser.add_argument("--out")
    parser.add_argument("--report", help="(dev) 결과 JSON으로 문서 생성")
    parser.add_argument("--test-report", help="test 확인 결과 JSON (주면 문서에 test 절 추가)")
    parser.add_argument("--output", default=str(ROOT / "docs/experiments/embedding_compare.md"))
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.report:
        report(args.report, args.output, args.test_report)
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
