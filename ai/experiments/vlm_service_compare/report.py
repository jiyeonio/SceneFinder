"""run.py 결과(라벨별 JSON)를 「끔」과 비교해 표와 판정을 냅니다 (기준: docs/design/vlm_search.md 「검증 계획」).

    python ai/experiments/vlm_service_compare/report.py --dir ~/scenefinder_eval/vlm_service --off off on_zmax2 on_zmax0 on_subfirst

지표는 개수로 셈: hit30·hit50 = 1위 IoU ≥ 0.3/0.5, r3 = NMS(IoU 0.5) 뒤 상위 3개 중 IoU ≥ 0.3, start5 = 1위 시작 ±5초.
S는 말 내용/화면 묘사로 나눔 (docs/experiments/eval_v2_s_query_kinds.tsv, 라벨의 s_kind가 있으면 그것).
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "translation_compare"))
import summary  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
KEYS = ("hit30", "hit50", "r3", "start5")
GROUPS = (("S", "S"), ("S_speech", "S 말 내용"), ("S_visual", "S 화면 묘사"), ("V", "V"))
NOISE = 3


def s_kinds(queries_path):
    kinds = {}
    tsv = ROOT / "docs/experiments/eval_v2_s_query_kinds.tsv"
    if tsv.exists():
        with open(tsv, encoding="utf-8") as f:
            kinds = {int(r["num"]): r["kind"] for r in csv.DictReader(f, delimiter="\t")}
    labels = json.loads(Path(queries_path).expanduser().read_text(encoding="utf-8"))
    for q in labels["queries"]:
        if q.get("s_kind"):
            kinds[q["num"]] = q["s_kind"]
    return kinds


def score_row(r):
    gts = [tuple(g) for g in r["gt"]]
    segs = [(m["start"], m["end"]) for m in r["moments"]]
    if not segs:
        return {"iou": 0.0, "hit30": 0, "hit50": 0, "r3": 0, "start5": 0, "top_source": None}
    x = summary.best_iou(segs[0], gts)
    top = summary.nms_top(segs)
    return {"iou": x, "hit30": int(x >= 0.3), "hit50": int(x >= 0.5),
            "r3": int(any(summary.best_iou(s, gts) >= 0.3 for s in top)),
            "start5": int(summary.start_ok(segs[0], gts)), "top_source": r["moments"][0]["source"],
            "top": segs[0]}


def group_of(r, kinds):
    if r["type"] == "V":
        return ["V"]
    return ["S", "S_speech" if kinds.get(r["num"]) == "말 내용" else "S_visual"]


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(0.95 * (len(xs) - 1)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--off", default="off")
    ap.add_argument("labels", nargs="+")
    a = ap.parse_args()
    d = Path(a.dir).expanduser()
    runs = {lb: json.loads((d / f"{lb}.json").read_text(encoding="utf-8")) for lb in [a.off] + a.labels}
    kinds = s_kinds(runs[a.off]["meta"]["queries"])

    res = {}
    for lb, run in runs.items():
        rows = {r["num"]: r for r in run["rows"]}
        sc = {n: score_row(r) for n, r in rows.items()}
        g = {k: {m: 0 for m in KEYS} | {"n": 0, "iou": 0.0} for k, _ in GROUPS}
        for n, r in rows.items():
            for k in group_of(r, kinds):
                g[k]["n"] += 1
                g[k]["iou"] += sc[n]["iou"]
                for m in KEYS:
                    g[k][m] += sc[n][m]
        for k in g:
            g[k]["iou"] = round(g[k]["iou"] / g[k]["n"], 3) if g[k]["n"] else 0.0
        res[lb] = {"rows": rows, "scores": sc, "groups": g,
                   "p50": statistics.median(r["ms"] for r in rows.values()),
                   "p95": p95([r["ms"] for r in rows.values()]),
                   "first_p95": p95([r["first_ms"] for r in rows.values()]),
                   "caption_sources": sum(1 for s in sc.values() if s["top_source"] == "caption")}

    off = res[a.off]
    print(f"질의 {len(off['rows'])}개 (" + ", ".join(f"{name} {off['groups'][k]['n']}" for k, name in GROUPS) + ")\n")
    print("| 방식 | " + " | ".join(f"{name} IoU≥0.3 / ≥0.5 / R@3 / 시작±5초" for _, name in GROUPS)
          + " | 1위가 설명문 | 응답 p50 / p95 (ms) | 첫 요청 p95 |")
    print("|---|" + "---|" * (len(GROUPS) + 3))
    for lb, x in res.items():
        cells = []
        for k, _ in GROUPS:
            g = x["groups"][k]
            cells.append(" / ".join(str(g[m]) for m in KEYS) + f" (평균 IoU {g['iou']:.2f})")
        print(f"| {lb} | " + " | ".join(cells)
              + f" | {x['caption_sources']} | {x['p50']:.0f} / {x['p95']:.0f} | {x['first_p95']:.0f} |")

    print("\n판정 (끔 대비)")
    for lb in a.labels:
        x = res[lb]
        dg = {k: {m: x["groups"][k][m] - off["groups"][k][m] for m in KEYS} for k, _ in GROUPS}
        checks = [
            ("S IoU≥0.3 감소 1개 이하", dg["S"]["hit30"] >= -1),
            ("S R@3 감소 1개 이하", dg["S"]["r3"] >= -1),
            ("말 내용 S IoU≥0.3 감소 없음", dg["S_speech"]["hit30"] >= 0),
            ("말 내용 S R@3 감소 없음", dg["S_speech"]["r3"] >= 0),
            (f"V IoU≥0.3 또는 R@3 +{NOISE + 1} 이상", dg["V"]["hit30"] > NOISE or dg["V"]["r3"] > NOISE),
            ("응답 p95 증가 200ms 이내", x["p95"] - off["p95"] <= 200),
        ]
        ok = all(c for _, c in checks)
        print(f"- {lb}: {'통과' if ok else '불통과'} | "
              + ", ".join(f"{name} {'O' if c else 'X'}" for name, c in checks)
              + " | 차이 " + "; ".join(f"{name} " + "/".join(f"{dg[k][m]:+d}" for m in KEYS) for k, name in GROUPS)
              + f"; p95 {x['p95'] - off['p95']:+.0f}ms")
        changed = [n for n, r in off["rows"].items() if r["type"] == "S"
                   and off["scores"][n].get("top") != x["scores"][n].get("top")]
        for n in changed:
            o, s = off["scores"][n], x["scores"][n]
            print(f"    S #{n} 1위 바뀜: {o.get('top')} IoU {o['iou']:.2f} → {s.get('top')} ({s['top_source']}) IoU {s['iou']:.2f}"
                  f" | {off['rows'][n]['query']}")


if __name__ == "__main__":
    main()
