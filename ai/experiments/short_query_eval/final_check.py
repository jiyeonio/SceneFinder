"""마지막 확인 실험: (a) 현재 서비스, M1 칸 나눠 채우기, M4 위치는 설명문·길이는 Moment-DETR, M1+M4.
기준: docs/experiments/short_query_eval.md 「마지막 확인 실험」

    # 1) 신호 후보 계산 (CPU 가능). --sets로 묶음 선택 (A, B, dev, C)
    CUDA_VISIBLE_DEVICES= python ai/experiments/short_query_eval/final_check.py signals --sets A B dev \
        --queries ~/scenefinder_eval/labels_draft.json --features ~/scenefinder_eval/results_v2_whisper_turbo_b8 \
        --out ~/scenefinder_eval/short_query_eval/final_signals.json
    # 2) M4 기준값 정하기 + 판정 후보 정하기 (세트 A·B·dev)
    python ai/experiments/short_query_eval/final_check.py tune --signals ~/scenefinder_eval/short_query_eval/final_signals.json
    # 3) 세트 C 판정 (한 번만)
    python ai/experiments/short_query_eval/final_check.py judge --signals <세트 C 신호 JSON> --choice <tune 결과 JSON>
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
sys.path.insert(0, str(ROOT / "ai/experiments/clip_third_signal"))   # run.py = clip_third_signal의 것 (이 폴더의 run.py보다 먼저)
# candidates.py는 이 스크립트 폴더(sys.path 끝쪽)에서 읽음
os.environ.setdefault("CAPTION_SEARCH_ENABLED", "1")

SCOPE_TSV = ROOT / "docs/experiments/clip_third_signal_scope.tsv"
KEEP = None               # 신호별 후보를 모두 저장 (상위만 저장하면 겹침이 많은 영상에서 top 5를 못 채움)
KS = (1, 3, 5)
LS = (60.0, 120.0, None)  # None = 제한 없음
NOISE = 3


# ===================== 1) 신호 후보 계산 =====================

def signals(a):
    from backend.services import indexer  # noqa: F401  backend/.env 읽기 (MiniLM 경로 등)
    from run import Signals  # clip_third_signal/run.py
    from backend.services import captions
    from backend.services.subtitles import load_subtitles
    from backend.services.translate import to_english

    labels = json.loads(Path(a.queries).expanduser().read_text(encoding="utf-8"))
    with open(SCOPE_TSV, encoding="utf-8") as f:
        scope = {int(r["num"]): r["scope"] for r in csv.DictReader(f, delimiter="\t")}
    qs = []
    for q in labels["queries"]:
        if q.get("query_style") == "short" and q.get("short_set") in a.sets:
            qs.append((q, f"short_{q['short_set']}"))
        elif "dev" in a.sets and q["num"] in scope and q.get("query_style") != "short":
            qs.append((q, "dev_broad" if scope[q["num"]] == "넓은 장면" else "dev_moment"))
    sig = Signals(a.features)
    rows = []
    for q, group in qs:
        key = q["video"]
        yid = labels["videos"][key]["youtube_id"]
        index = captions.load_index(yid)
        subtitles, lang = load_subtitles(yid)
        subtitles = subtitles if (lang == "ko" and subtitles) else []
        sub = sig.subtitle(yid, subtitles, q["query"]) if subtitles else None
        cap = sig.caption(index, q["query"])
        detr = sig.detr(key, to_english(q["query"]))
        strip = lambda l: [{k: m[k] for k in ("start_time", "end_time", "score", "z", "source")} for m in l[:KEEP]]  # noqa: E731
        rows.append({"num": q["num"], "group": group, "video": key, "query": q["query"], "gt": q["gt"],
                     "duration": float(index["meta"]["duration"]),
                     "sub": [strip(sub[0]), sub[1]] if sub else None, "cap": [strip(cap[0]), cap[1]],
                     "detr": [strip(detr[0]), detr[1]]})
        print(f"#{q['num']} {group} {q['query']}", flush=True)
    out = Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": {"sets": a.sets, "device": "cpu", "queries": str(a.queries), "features": str(a.features),
                                        "at": time.strftime("%Y-%m-%d %H:%M:%S")}, "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("저장:", out)


# ===================== 방법 =====================

def methods_for(r, K=None, L=None):
    """저장한 신호로 (a), M1, M4(K, L), M1+M4(K, L) 결과."""
    from run import fuse          # clip_third_signal/run.py
    from candidates import slot_fill
    from backend.services.search_api import _widen_subtitle
    from backend.services import captions

    expand = captions._cfg()["expand"]
    ov, dur = captions._overlap, r["duration"]
    sub = tuple(r["sub"]) if r["sub"] else None
    cap = tuple(r["cap"])
    detr = r["detr"][0]
    sub_l = sub[0] if sub else []
    out = {"a": fuse(sub, cap, None, dur, _widen_subtitle, expand, ov)[0],
           "M1": slot_fill([cap[0], detr, sub_l], dur, _widen_subtitle, expand, ov)}
    if K is None:
        return out

    def located(top):
        """설명문 1위(확장 후)의 가운데를 포함하는, 상위 K개 안 가장 높은 Moment-DETR 구간 (길이 L 이하)."""
        mid = (max(0.0, top["start_time"] - expand) + min(dur, top["end_time"] + expand)) / 2
        for m in detr[:K]:
            if m["start_time"] <= mid <= m["end_time"] and (L is None or m["end_time"] - m["start_time"] <= L):
                return {**m, "source": "caption_detr", "z": top["z"]}
        return None

    first_a = out["a"][0]["source"] if out["a"] else None
    rep = located(cap[0][0]) if cap[0] else None
    cap_r = ([rep] + cap[0][1:], cap[1]) if rep else cap
    out["M4"] = fuse(sub, cap_r, None, dur, _widen_subtitle, expand, ov)[0] if (rep and first_a == "caption") else out["a"]
    out["M1+M4"] = slot_fill([cap_r[0], detr, sub_l], dur, _widen_subtitle, expand, ov) if rep else out["M1"]
    return out


def metrics(r, moments):
    import summary
    gts = [tuple(g) for g in r["gt"]]
    segs = [(x["start_time"], x["end_time"]) for x in moments]
    if not segs:
        return (0, 0, 0)
    t = segs[0]
    mid = (t[0] + t[1]) / 2
    return (int(any(a <= mid <= b for a, b in gts)),
            int(any(summary.best_iou(s, gts) >= 0.3 for s in summary.nms_top(segs))),
            int(summary.best_iou(t, gts) >= 0.3))


def totals(rows, m, K=None, L=None):
    v = [metrics(r, methods_for(r, K, L)[m]) for r in rows]
    return tuple(sum(x[i] for x in v) for i in range(3))


def existing_ok(rows, m, K=None, L=None):
    """기존 세트(dev 특정 순간·넓은 장면)에서 (a)보다 4개 이상 준 지표가 없으면 True."""
    for g in ("dev_moment", "dev_broad"):
        rs = [r for r in rows if r["group"] == g]
        ta, tm = totals(rs, "a"), totals(rs, m, K, L)
        if any(tm[i] - ta[i] <= -(NOISE + 1) for i in range(3)):
            return False
    return True


def fmt(t):
    return " / ".join(map(str, t))


# ===================== 2) 기준값·판정 후보 정하기 =====================

def tune(a):
    data = json.loads(Path(a.signals).expanduser().read_text(encoding="utf-8"))
    rows = data["rows"]
    AB = [r for r in rows if r["group"] in ("short_A", "short_B")]
    groups = [("세트 A", "short_A"), ("세트 B", "short_B"), ("dev 특정 순간", "dev_moment"), ("dev 넓은 장면", "dev_broad")]
    print("### M4·M1+M4 기준값 후보 (각 칸: hit-in-GT / R@3 / IoU≥0.3)\n")
    print("| 방법 | K | L | 세트 A+B (53) | " + " | ".join(n for n, _ in groups) + " | 기존 세트 조건 |")
    print("|---|---|---|---|" + "---|" * len(groups) + "---|")
    best = {}
    for m in ("M4", "M1+M4"):
        for K in KS:
            for L in LS:
                ok = existing_ok(rows, m, K, L)
                ab = totals(AB, m, K, L)
                cells = [fmt(totals([r for r in rows if r["group"] == g], m, K, L)) for _, g in groups]
                print(f"| {m} | {K} | {'없음' if L is None else int(L)} | {fmt(ab)} | " + " | ".join(cells) + f" | {'만족' if ok else '불만족'} |")
                if ok:
                    keyv = (ab, -K, -(L if L is not None else 1e9))
                    if m not in best or keyv > best[m][0]:
                        best[m] = (keyv, K, L)
    print()
    for m in ("a", "M1"):
        cells = [fmt(totals([r for r in rows if r["group"] == g], m)) for _, g in groups]
        print(f"| {m} | - | - | {fmt(totals(AB, m))} | " + " | ".join(cells) + f" | {'-' if m == 'a' else ('만족' if existing_ok(rows, m) else '불만족')} |")
    choice = {m: {"K": v[1], "L": v[2]} for m, v in best.items()}
    print("\n고른 기준값:", {m: (c["K"], "없음" if c["L"] is None else c["L"]) for m, c in choice.items()})

    # 판정 후보: M1, M4, M1+M4 중 기존 세트 조건 만족 + 세트 A+B hit-in-GT 최대
    cands = []
    order = {"M4": 0, "M1": 1, "M1+M4": 2}
    if existing_ok(rows, "M1"):
        cands.append(("M1", None, None))
    for m, c in choice.items():
        cands.append((m, c["K"], c["L"]))
    if not cands:
        print("판정 후보 없음")
        judge_m = None
    else:
        judge_m = max(cands, key=lambda x: (totals(AB, x[0], x[1], x[2]), -order[x[0]]))
        print(f"판정 후보: {judge_m[0]} (K={judge_m[1]}, L={judge_m[2]}), 세트 A+B {fmt(totals(AB, judge_m[0], judge_m[1], judge_m[2]))}"
              f" vs (a) {fmt(totals(AB, 'a'))}")
    if a.save:
        Path(a.save).expanduser().write_text(json.dumps({"params": choice, "judge": judge_m, "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                                                        ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장:", a.save)


# ===================== 3) 세트 C 판정 =====================

def judge(a):
    data = json.loads(Path(a.signals).expanduser().read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if r["group"] == "short_C"]
    ch = json.loads(Path(a.choice).expanduser().read_text(encoding="utf-8"))
    jm, jK, jL = ch["judge"]
    ta = totals(rows, "a")
    print(f"세트 C ({len(rows)}개), 각 칸: hit-in-GT / R@3 / IoU≥0.3\n")
    print("| 방법 | 세트 C | (a) 대비 |")
    print("|---|---|---|")
    print(f"| (a) 현재 서비스 | {fmt(ta)} | - |")
    for m in ("M1", "M4", "M1+M4"):
        K, L = (None, None) if m == "M1" else (ch["params"][m]["K"], ch["params"][m]["L"])
        t = totals(rows, m, K, L)
        tag = " **(판정 후보)**" if m == jm else " (참고)"
        print(f"| {m}{tag} | {fmt(t)} | " + " / ".join(f"{t[i] - ta[i]:+d}" for i in range(3)) + " |")
    tj = totals(rows, jm, jK, jL)
    d = [tj[i] - ta[i] for i in range(3)]
    ok = (d[0] >= NOISE + 1 or d[1] >= NOISE + 1) and all(x > -2 for x in d)
    print(f"\n판정: {jm} 차이 {d} → {'개선 확인' if ok else '개선 확인 안 됨'}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("signals")
    s.add_argument("--sets", nargs="+", required=True)
    s.add_argument("--queries", required=True)
    s.add_argument("--features", required=True)
    s.add_argument("--out", required=True)
    t = sp.add_parser("tune")
    t.add_argument("--signals", required=True)
    t.add_argument("--save")
    j = sp.add_parser("judge")
    j.add_argument("--signals", required=True)
    j.add_argument("--choice", required=True)
    a = ap.parse_args()
    {"signals": signals, "tune": tune, "judge": judge}[a.cmd](a)


if __name__ == "__main__":
    main()
