"""실사용 짧은 질의(query_style: short) 평가. 문서: docs/experiments/short_query_eval.md

    CUDA_VISIBLE_DEVICES= python ai/experiments/short_query_eval/run.py --queries ~/scenefinder_eval/labels_draft.json \
        --features ~/scenefinder_eval/results_v2_whisper_turbo_b8 --out ~/scenefinder_eval/short_query_eval
    python ai/experiments/short_query_eval/run.py --report ~/scenefinder_eval/short_query_eval/results.json

- (a) 현재 서비스(자막 + 설명문, captions.fused_search와 같은 규칙), (b) Moment-DETR 단독(NLLB 번역 + predict_moments_hybrid),
  (c) 자막만(MiniLM, 서비스 구간 보정), (d) 설명문만(e5, 앞뒤 2초 확장). 모두 영상마다 top 5
- dev/test 구분 없이 짧은 질의 전체. 정답 구간이 여러 개면 하나라도 맞으면 정답
- 자막·설명문 파일은 서비스 서버의 파일(data/processed/)을 읽기만 함
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai/experiments/translation_compare"))
sys.path.insert(0, str(ROOT / "ai/experiments/clip_third_signal"))
os.environ.setdefault("CAPTION_SEARCH_ENABLED", "1")

METHODS = (("a", "(a) 현재 서비스"), ("b", "(b) Moment-DETR 단독"), ("c", "(c) 자막만"), ("d", "(d) 설명문만"))


def run(a):
    from run import TOP_K, Signals, fuse  # clip_third_signal/run.py

    from backend.services import captions
    from backend.services.search_api import _widen_subtitle
    from backend.services.subtitles import load_subtitles
    from backend.services.translate import to_english

    labels = json.loads(Path(a.queries).expanduser().read_text(encoding="utf-8"))
    qs = [q for q in labels["queries"] if q.get("query_style") == "short"]
    sig = Signals(a.features)
    expand = sig.cfg["expand"]

    def no_save_embeddings(youtube_video_id, wins, model):   # fused_search가 data/에 캐시를 쓰지 않도록
        return model.encode([w["text"] for w in wins], convert_to_tensor=True).float().cpu()
    captions._subtitle_embeddings = no_save_embeddings

    rows, mismatch = [], []
    for q in qs:
        key = q["video"]
        yid = labels["videos"][key]["youtube_id"]
        index = captions.load_index(yid)
        duration = float(index["meta"]["duration"])
        subtitles, lang = load_subtitles(yid)
        subtitles = subtitles if (lang == "ko" and subtitles) else []
        sub = sig.subtitle(yid, subtitles, q["query"]) if subtitles else None
        cap = sig.caption(index, q["query"])
        en = to_english(q["query"])
        detr = sig.detr(key, en)
        only = lambda lst: fuse(None, (lst, False), None, duration, _widen_subtitle, expand, captions._overlap)[0] if lst else []  # noqa: E731
        res = {
            "a": fuse(sub, cap, None, duration, _widen_subtitle, expand, captions._overlap)[0],
            "b": only(detr[0]),
            "c": only(sub[0] if sub else []),
            "d": only(cap[0]),
        }
        fs = captions.fused_search(yid, q["query"], TOP_K, subtitles, index, _widen_subtitle, sig.minilm, threading.Lock())
        if [(m["start_time"], m["end_time"], m["source"]) for m in fs] != [(m["start_time"], m["end_time"], m["source"]) for m in res["a"]]:
            mismatch.append(q["num"])
        rows.append({"num": q["num"], "video": key, "youtube_id": yid, "type": q["type"], "query": q["query"], "query_en": en,
                     "gt": q["gt"], "duration": duration, "has_subtitles": bool(subtitles), **{k: {"moments": v} for k, v in res.items()}})
        print(f"#{q['num']} {q['query']} → a={res['a'][0]['start_time']:.0f}s", flush=True)
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    meta = {"queries": str(a.queries), "features": str(a.features), "device": "cpu", "top_k": TOP_K,
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "a_vs_fused_search_mismatch": mismatch}
    (out / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"(a) vs captions.fused_search: {len(rows)}개 중 다른 질의 {len(mismatch)}개 {mismatch}")
    print("저장:", out / "results.json")


def report(path):
    import summary
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    rows = data["rows"]

    def metrics(r, m):
        gts = [tuple(g) for g in r["gt"]]
        segs = [(x["start_time"], x["end_time"]) for x in r[m]["moments"]]
        if not segs:
            return 0, 0, 0
        top1 = segs[0]
        mid = (top1[0] + top1[1]) / 2
        hit = any(a <= mid <= b for a, b in gts)
        r3 = any(summary.best_iou(s, gts) >= 0.3 for s in summary.nms_top(segs))
        return int(hit), int(r3), int(summary.best_iou(top1, gts) >= 0.3)

    def gt_share(r):
        return sum(b - a for a, b in r["gt"]) / r["duration"]

    groups = [
        ("전체", lambda r: True),
        ("자막 있는 영상", lambda r: r["has_subtitles"]),
        ("자막 없는 영상", lambda r: not r["has_subtitles"]),
        ("정답이 영상의 30% 미만", lambda r: gt_share(r) < 0.3),
        ("정답이 영상의 30% 이상", lambda r: gt_share(r) >= 0.3),
    ]
    print("| 묶음 (질의 수) | " + " | ".join(n for _, n in METHODS) + " |")
    print("|---|" + "---|" * len(METHODS))
    for name, fn in groups:
        rs = [r for r in rows if fn(r)]
        if not rs:
            continue
        cells = []
        for m, _ in METHODS:
            v = [metrics(r, m) for r in rs]
            cells.append(" / ".join(str(sum(x[i] for x in v)) for i in range(3)))
        print(f"| {name} ({len(rs)}) | " + " | ".join(cells) + " |")
    print("\n각 칸: hit-in-GT / R@3 / IoU≥0.3 (개수)")
    print("\n질의별 (✓ = hit-in-GT, 괄호는 1위 구간)")
    print("| # | 영상 | 질의 | 정답 비율 | " + " | ".join(n for _, n in METHODS) + " |")
    print("|---|---|---|---|" + "---|" * len(METHODS))
    for r in rows:
        cells = []
        for m, _ in METHODS:
            mm = r[m]["moments"]
            if not mm:
                cells.append("결과 없음")
                continue
            hit = metrics(r, m)[0]
            cells.append(f"{'✓ ' if hit else ''}{mm[0]['start_time']:.0f}–{mm[0]['end_time']:.0f}")
        print(f"| {r['num']} | {r['video']} | {r['query']} | {100 * gt_share(r):.0f}% | " + " | ".join(cells) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries")
    ap.add_argument("--features")
    ap.add_argument("--out")
    ap.add_argument("--report")
    a = ap.parse_args()
    if a.report:
        report(a.report)
    else:
        run(a)


if __name__ == "__main__":
    main()
