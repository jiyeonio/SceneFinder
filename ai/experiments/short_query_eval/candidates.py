"""칸 나눠 채우기(M1)·구간 이어붙이기(M2)·조합(M3)을 현재 서비스(a)와 비교. 기준: docs/experiments/short_query_eval.md

    CUDA_VISIBLE_DEVICES= python ai/experiments/short_query_eval/candidates.py --queries ~/scenefinder_eval/labels_draft.json \
        --features ~/scenefinder_eval/results_v2_whisper_turbo_b8 --out ~/scenefinder_eval/short_query_eval
    python ai/experiments/short_query_eval/candidates.py --report ~/scenefinder_eval/short_query_eval/candidates.json

질의 묶음: 짧은 질의 세트 A·B(short_set), dev 특정 순간·넓은 장면(docs/experiments/clip_third_signal_scope.tsv)
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai/experiments/translation_compare"))
sys.path.insert(0, str(ROOT / "ai/experiments/clip_third_signal"))
os.environ.setdefault("CAPTION_SEARCH_ENABLED", "1")

SCOPE_TSV = ROOT / "docs/experiments/clip_third_signal_scope.tsv"
MAX_MERGE_SEC = 120.0
DELTAS = (0.5, 1.0)
CANDIDATES = ["M1", "M2-0.5", "M2-1.0", "M3-0.5", "M3-1.0"]
METHODS = ["a"] + CANDIDATES


def merged_caption_span(index, scores, z, top, delta, duration, expand):
    """설명문 1위 창(top)의 2초 칸에서 시작해, 이웃 1칸 창의 z가 top의 z − delta 이상이면 붙임 (최대 120초)."""
    caps = index["captions"]
    n = len(caps)                     # windows의 앞 n개가 1칸짜리 창 (captions.windows 순서)
    inside = [i for i in range(n) if caps[i]["start_time"] >= top["start_time"] - 1e-6 and caps[i]["end_time"] <= top["end_time"] + 1e-6]
    lo, hi = min(inside), max(inside)
    floor = top["z"] - delta
    while True:
        length = caps[hi]["end_time"] - caps[lo]["start_time"]
        cands = []
        if lo > 0 and z[lo - 1] >= floor:
            cands.append((z[lo - 1], "l"))
        if hi < n - 1 and z[hi + 1] >= floor:
            cands.append((z[hi + 1], "r"))
        if not cands:
            break
        side = max(cands)[1]
        nlo, nhi = (lo - 1, hi) if side == "l" else (lo, hi + 1)
        if caps[nhi]["end_time"] - caps[nlo]["start_time"] > MAX_MERGE_SEC:
            break
        lo, hi = nlo, nhi
    return {"start_time": round(max(0.0, caps[lo]["start_time"] - expand), 2),
            "end_time": round(min(duration, caps[hi]["end_time"] + expand), 2),
            "score": top["score"], "z": top["z"], "source": "caption_merged",
            "merged_sec": round(caps[hi]["end_time"] - caps[lo]["start_time"], 1)}


def slot_fill(lists, duration, widen, expand, overlap, top_k=5):
    """M1: [설명문, Moment-DETR, 자막] 순서로 한 칸씩. 겹치면 같은 신호의 다음 후보."""
    def span(m):
        if m["source"] == "subtitle":
            return widen([{"start_time": m["start_time"], "end_time": m["end_time"], "source": "subtitle"}])[0]
        if m["source"] == "caption":
            return {"start_time": round(max(0.0, m["start_time"] - expand), 2), "end_time": round(min(duration, m["end_time"] + expand), 2)}
        return {"start_time": round(m["start_time"], 2), "end_time": round(m["end_time"], 2)}
    lists = [l for l in lists if l]
    merged, idx = [], [0] * len(lists)
    while len(merged) < top_k and any(idx[j] < len(lists[j]) for j in range(len(lists))):
        for j in range(len(lists)):
            while idx[j] < len(lists[j]):
                m = lists[j][idx[j]]
                idx[j] += 1
                s = span(m)
                c = {"start_time": s["start_time"], "end_time": s["end_time"], "score": round(float(m["score"]), 4), "source": m["source"]}
                if all(overlap(c, k) < 0.5 for k in merged):
                    merged.append(c)
                    break
            if len(merged) >= top_k:
                break
    return merged


def run(a):
    from run import Signals, fuse  # clip_third_signal/run.py

    from backend.services import captions
    from backend.services.search_api import _widen_subtitle
    from backend.services.subtitles import load_subtitles
    from backend.services.translate import to_english

    labels = json.loads(Path(a.queries).expanduser().read_text(encoding="utf-8"))
    with open(SCOPE_TSV, encoding="utf-8") as f:
        scope = {int(r["num"]): r["scope"] for r in csv.DictReader(f, delimiter="\t")}
    qs = []
    for q in labels["queries"]:
        if q.get("query_style") == "short":
            qs.append((q, f"short_{q['short_set']}"))
        elif q["num"] in scope:
            qs.append((q, "dev_broad" if scope[q["num"]] == "넓은 장면" else "dev_moment"))
    sig = Signals(a.features)
    expand = sig.cfg["expand"]
    rows = []
    for q, group in qs:
        key = q["video"]
        yid = labels["videos"][key]["youtube_id"]
        index = captions.load_index(yid)
        duration = float(index["meta"]["duration"])
        subtitles, lang = load_subtitles(yid)
        subtitles = subtitles if (lang == "ko" and subtitles) else []
        sub = sig.subtitle(yid, subtitles, q["query"]) if subtitles else None
        # 설명문: 창 순서 그대로의 점수·z (이어붙이기용)와 점수순 목록
        qv = captions._encode_e5([q["query"]], sig.cfg["embed_model"], "query: ")[0].float().cpu()
        scores = (index["emb"].float() @ qv).tolist()
        z = captions._zscores(scores)
        cap_l = sorted([{**w, "score": s, "z": (z[i] if z else None), "source": "caption"}
                        for i, (w, s) in enumerate(zip(index["windows"], scores))], key=lambda m: -m["score"])
        cap = (cap_l, z is not None)
        detr = sig.detr(key, to_english(q["query"]))
        res = {"a": fuse(sub, cap, None, duration, _widen_subtitle, expand, captions._overlap)[0]}
        res["M1"] = slot_fill([cap_l, detr[0], sub[0] if sub else []], duration, _widen_subtitle, expand, captions._overlap)
        for d in DELTAS:
            if z is None:   # z를 못 쓰면 이어붙이지 않음 (그대로)
                res[f"M2-{d}"], res[f"M3-{d}"] = res["a"], res["M1"]
                continue
            m = merged_caption_span(index, scores, z, cap_l[0], d, duration, expand)
            cap_m = [m] + cap_l[1:]
            res[f"M2-{d}"] = fuse(sub, (cap_m, True), None, duration, _widen_subtitle, expand, captions._overlap)[0]
            res[f"M3-{d}"] = slot_fill([cap_m, detr[0], sub[0] if sub else []], duration, _widen_subtitle, expand, captions._overlap)
        rows.append({"num": q["num"], "group": group, "video": key, "type": q["type"], "query": q["query"], "gt": q["gt"],
                     "duration": duration, "has_subtitles": bool(subtitles), "source": q.get("source"),
                     **{k: {"moments": v} for k, v in res.items()}})
        print(f"#{q['num']} {group} {q['query']}", flush=True)
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    meta = {"queries": str(a.queries), "features": str(a.features), "device": "cpu", "deltas": DELTAS,
            "max_merge_sec": MAX_MERGE_SEC, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out / "candidates.json").write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", out / "candidates.json")


def metrics(r, m):
    import summary
    gts = [tuple(g) for g in r["gt"]]
    segs = [(x["start_time"], x["end_time"]) for x in r[m]["moments"]]
    if not segs:
        return 0, 0, 0
    top1 = segs[0]
    mid = (top1[0] + top1[1]) / 2
    return (int(any(a <= mid <= b for a, b in gts)),
            int(any(summary.best_iou(s, gts) >= 0.3 for s in summary.nms_top(segs))),
            int(summary.best_iou(top1, gts) >= 0.3))


def totals(rows, m):
    v = [metrics(r, m) for r in rows]
    return tuple(sum(x[i] for x in v) for i in range(3))


def report(path):
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    rows = data["rows"]
    share = lambda r: sum(b - a for a, b in r["gt"]) / r["duration"]  # noqa: E731
    groups = [
        ("세트 A (선택용)", lambda r: r["group"] == "short_A"),
        ("세트 A · 정답 90% 미만", lambda r: r["group"] == "short_A" and share(r) < 0.9),
        ("dev 특정 순간", lambda r: r["group"] == "dev_moment"),
        ("dev 넓은 장면", lambda r: r["group"] == "dev_broad"),
        ("세트 B (확인용)", lambda r: r["group"] == "short_B"),
        ("세트 B · 정답 90% 미만", lambda r: r["group"] == "short_B" and share(r) < 0.9),
    ]
    G = {name: [r for r in rows if fn(r)] for name, fn in groups}
    print("| 묶음 (질의 수) | " + " | ".join(METHODS) + " |")
    print("|---|" + "---|" * len(METHODS))
    for name, rs in G.items():
        print(f"| {name} ({len(rs)}) | " + " | ".join(" / ".join(map(str, totals(rs, m))) for m in METHODS) + " |")
    print("\n각 칸: hit-in-GT / R@3 / IoU≥0.3 (개수)\n")

    # 고르기 (세트 A + 기존 세트 조건)
    ok = []
    for m in CANDIDATES:
        fine = all(totals(G[g], m)[i] - totals(G[g], "a")[i] > -2 for g in ("dev 특정 순간", "dev 넓은 장면") for i in range(3))
        print(f"- {m}: 세트 A {totals(G['세트 A (선택용)'], m)}, 기존 세트 조건 {'만족' if fine else '불만족'}")
        if fine:
            ok.append(m)
    if not ok:
        print("→ 채택 없음")
        return
    best = max(ok, key=lambda m: totals(G["세트 A (선택용)"], m))
    print(f"→ 고른 후보: {best}")
    ta, tb = totals(G["세트 B (확인용)"], "a"), totals(G["세트 B (확인용)"], best)
    diff = [tb[i] - ta[i] for i in range(3)]
    improved = (diff[0] >= 4 or diff[1] >= 4) and all(d > -2 for d in diff)
    print(f"세트 B: (a) {ta} → {best} {tb}, 차이 {diff} → {'개선 확인' if improved else '개선 확인 안 됨'}")
    import statistics as st
    print("\n이어붙인 설명문 구간(1위가 설명문인 질의에서, 앞뒤 2초 확장 포함 길이)")
    for m in CANDIDATES[1:]:
        for name, rs in G.items():
            if "90%" in name:
                continue
            lens = [x["end_time"] - x["start_time"] for r in rs for x in r[m]["moments"][:1] if x["source"] == "caption_merged"]
            base = "a" if m.startswith("M2") else "M1"
            changed = sum(1 for r in rs if [(x["start_time"], x["end_time"]) for x in r[m]["moments"][:1]]
                          != [(x["start_time"], x["end_time"]) for x in r[base]["moments"][:1]])
            if lens:
                print(f"- {m} · {name}: 1위가 이어붙인 구간 {len(lens)}/{len(rs)}개, 길이 중앙값 {st.median(lens):.0f}초"
                      f" (범위 {min(lens):.0f}~{max(lens):.0f}), 1위가 {'(a)' if m.startswith('M2') else 'M1'}와 다른 질의 {changed}개")


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
