"""예비 실험 결과(prelim_eval.py 출력)를 표로 집계해 마크다운으로 쓴다.

    python ai/experiments/vlm_model/prelim_report.py --res ai/experiments/vlm_model/results/prelim_dev \
        --out docs/experiments/vlm_prelim_dev_tables.md
"""
import argparse, json, statistics, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ai/experiments/translation_compare"))
import summary  # noqa: E402

LABEL = {"B1": "B1 자막 검색 (MiniLM)", "B2": "B2 구간 검색 CLIP 버전 (NLLB 번역 + Moment-DETR)", "B3": "B3 main 서비스 결합",
         "F-CLIP": "화면 검색: 다국어 CLIP", "F-VLM": "화면 검색: Qwen3-VL-Embedding-2B (학습 없음)",
         "F-VLM-1280": "(참고) 화면 검색 Qwen3-VL-Emb 1280×720", "REF-SUB-VLM": "(참고) 자막 검색 Qwen3-VL-Emb 텍스트"}


def metrics(rows, n):
    if not rows:
        return None
    t1 = [r[n]["iou"] for r in rows]
    top = [r[n]["top5"] for r in rows]
    hit = lambda segs, gt: any(summary.best_iou(s, gt) >= 0.3 for s in segs)  # noqa: E731
    return {"n": len(rows),
            "r1_03": sum(x >= 0.3 for x in t1), "r1_05": sum(x >= 0.5 for x in t1),
            "r3": sum(hit(t[:3], r["gt"]) for t, r in zip(top, rows)),
            "r5": sum(hit(t[:5], r["gt"]) for t, r in zip(top, rows)),
            "start5": sum(bool(t) and summary.start_ok(t[0], r["gt"]) for t, r in zip(top, rows)),
            "miou": statistics.mean(t1)}


def rand_metrics(rows):
    return {"n": len(rows), "r1_03": sum(r["random"]["p03"] for r in rows), "r1_05": sum(r["random"]["p05"] for r in rows),
            "miou": statistics.mean(r["random"]["iou_mean"] for r in rows)}


def pct(k, n):
    return f"{k / n * 100:.0f}% ({k:.0f}/{n})" if n else "–"


GROUPS = [("전체", lambda r: True), ("S 말", lambda r: r["type"] == "S"), ("V 화면", lambda r: r["type"] == "V"),
          ("V 화면 글자", lambda r: r["type"] == "V" and r["overlay_text"]),
          ("AI 초안 질의", lambda r: r["origin"] == "ai_draft"), ("사용자 질문", lambda r: r["origin"] == "simulated_user"),
          ("부분 답", lambda r: r["partial"])]


def sim_no_answer(rows, negs):
    """사용자 질문(simulated_user) 중 영상에 답이 없는 비율. 유형·애매함·의도는 vlm_eval_sim_queries.json에서."""
    sim = {q["query"]: q for qs in json.loads((ROOT / "docs/experiments/vlm_eval_sim_queries.json").read_text())["queries"].values() for q in qs}
    ans = [r for r in rows if r["origin"] == "simulated_user"]; no = [x for x in negs if x["origin"] == "simulated_user"]
    tot = len(ans) + len(no)
    L = [f"\n### 사용자 질문 중 영상에 답이 없는 비율 (n={tot})\n",
         f"- 정답 없음 {pct(len(no), tot)}, 답 있음 {pct(len(ans), tot)} (그중 부분 답 {sum(r['partial'] for r in ans)}개)\n",
         "| 구분 | 값 | 정답 없음 / 전체 |", "|---|---|---|"]
    for field, name in (("persona", "사용자 유형"), ("vague", "애매한 질문"), ("intent", "질문 의도")):
        c_all, c_no = Counter(), Counter()
        for q, is_no in [(r["query"], False) for r in ans] + [(x["query"], True) for x in no]:
            v = sim.get(q, {}).get(field, "?"); v = v.split(":")[0] if isinstance(v, str) else v
            c_all[v] += 1; c_no[v] += is_no
        for v in sorted(c_all, key=str):
            L.append(f"| {name} | {v} | {c_no[v]}/{c_all[v]} |")
    L.append("\n정답 없음인 사용자 질문:\n")
    L += [f"- {x['video']}: 「{x['query']}」" for x in no]
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = Path(a.res)
    rows = json.loads((res / "rows.json").read_text()); negs = json.loads((res / "negatives.json").read_text())
    meta = json.loads((res / "meta.json").read_text()); methods = meta["methods"]
    L = []
    L.append("각 칸: 비율 (개수/질의 수). R@1 = 1위 구간 IoU 기준, R@3·R@5 = 상위 3·5개 중 IoU ≥ 0.3이 하나라도 있음(앞 후보와 IoU ≥ 0.5로 겹치는 후보는 건너뜀), 시작 ±5초 = 1위 구간 시작이 정답 시작 ±5초 안.\n")
    for gname, f in GROUPS:
        sub = [r for r in rows if f(r)]
        if not sub:
            continue
        L.append(f"### {gname} (n={len(sub)})\n")
        L.append("| 방식 | R@1 IoU≥0.3 | R@1 IoU≥0.5 | R@3 | R@5 | 시작 ±5초 | 평균 IoU |")
        L.append("|---|---|---|---|---|---|---|")
        for n in methods:
            m = metrics(sub, n)
            L.append(f"| {LABEL[n]} | {pct(m['r1_03'], m['n'])} | {pct(m['r1_05'], m['n'])} | {pct(m['r3'], m['n'])} | "
                     f"{pct(m['r5'], m['n'])} | {pct(m['start5'], m['n'])} | {m['miou']:.3f} |")
        rm = rand_metrics(sub)
        L.append(f"| 무작위 기준선 (기댓값) | {rm['r1_03'] / rm['n'] * 100:.0f}% | {rm['r1_05'] / rm['n'] * 100:.0f}% | – | – | – | {rm['miou']:.3f} |\n")
    # 영상별
    L.append("### 영상별 R@1 IoU≥0.3 개수\n")
    vids = sorted({r["video"] for r in rows})
    L.append("| 방식 | " + " | ".join(vids) + " |"); L.append("|---|" + "---|" * len(vids))
    for n in methods:
        L.append(f"| {LABEL[n]} | " + " | ".join(f"{sum(r[n]['iou'] >= 0.3 for r in rows if r['video'] == v)}/{sum(r['video'] == v for r in rows)}" for v in vids) + " |")
    # 시간·메모리
    L.append("\n### 시간·메모리\n")
    L.append("| 방식 | 질의당 응답 중앙값 | 95% |"); L.append("|---|---|---|")
    for n in methods:
        t = meta["latency_sec"][n]; L.append(f"| {LABEL[n]} | {t['median'] * 1000:.0f} ms | {t['p95'] * 1000:.0f} ms |")
    L.append(f"\n- Qwen3-VL-Embedding-2B 프레임 특징 추출(dev 실측): 640×360 영상 1분당 {meta['extraction_sec_per_video_min']['qwen_640']}초, "
             f"1280×720 {meta['extraction_sec_per_video_min']['qwen_1280']}초")
    L.append(f"- 질의 실행 중 GPU 최대 할당: {meta['gpu_peak_gib_during_queries']} GiB (평가 스크립트에 올린 모든 모델 합)")
    # 정답 없음: 1위 점수 분포
    L.append(f"\n### 정답 없음 질의 (n={len(negs)}): 1위 점수 분포 (임계값은 아직 정하지 않음)\n")
    L.append("| 방식 | 정답 없음 질의 1위 점수 중앙값 [최소–최대] | 정답 있는 질의 1위 점수 중앙값 [최소–최대] |"); L.append("|---|---|---|")
    for n in methods:
        ns = [x[n] for x in negs if x.get(n) is not None]; ps = [r[n]["score"] for r in rows if r[n].get("score") is not None]
        if ns and ps:
            L.append(f"| {LABEL[n]} | {statistics.median(ns):.3f} [{min(ns):.3f}–{max(ns):.3f}] | {statistics.median(ps):.3f} [{min(ps):.3f}–{max(ps):.3f}] |")
    L += sim_no_answer(rows, negs)
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
