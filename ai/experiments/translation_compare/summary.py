"""run.py·fusion.py 결과를 질의 묶음별로 집계합니다.

묶음: 전체 / S / V / V·화면 글자 있음 / V·화면 글자 없음 / V·화면 글자 미표시 / source별(ai_draft·human_reviewed·human)
      / split별(dev·test, eval_youtube_videos.tsv에 있는 영상만)
지표:
- mean_iou: 1위 구간 평균 IoU
- hit30, hit50: 1위 구간 IoU ≥ 0.3 / ≥ 0.5 비율
- r3: 상위 3개 구간 중 하나라도 IoU ≥ 0.3인 비율 (R@3). 후보는 각 방식의 순위대로, 앞 순위와 IoU ≥ 0.5로 겹치는 후보는
  중복으로 보고 뺀 뒤(NMS) 3개. 결과 행에 top3가 없으면(예전 결과) None
- start5: 1위 구간 시작이 정답 시작(여러 개면 가장 가까운 것) ±5초 안인 비율
결과가 없는 방식(예: 자막 없는 영상의 (d))은 모든 지표를 0으로 셉니다.
"""
import query_set

METRICS = ("mean_iou", "hit30", "hit50", "r3", "start5")
NMS_IOU = 0.5        # 이보다 많이 겹치는 아래 순위 후보는 중복으로 봄
TOP_K = 3
START_TOL = 5.0      # 시작점 오차 허용(초)


def iou(a, b):
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union > 0 else 0.0


def best_iou(seg, gts):
    return max(iou(seg, g) for g in gts)


def nms_top(segs, k=TOP_K, thr=NMS_IOU):
    """순위대로 정렬된 구간 목록에서 앞 순위와 많이 겹치는 것을 빼고 k개."""
    kept = []
    for s in segs:
        s = (float(s[0]), float(s[1]))
        if all(iou(s, t) < thr for t in kept):
            kept.append(s)
        if len(kept) == k:
            break
    return kept


def start_ok(seg, gts, tol=START_TOL):
    return min(abs(seg[0] - g[0]) for g in gts) <= tol


def annotate(row, qs):
    """결과 행에 질의의 source·overlay_text·split을 붙임."""
    row.update(qs.info[row["num"]])
    return row


def groups(rows):
    """(묶음 이름, 행 목록). 빈 묶음은 뺌."""
    V = [r for r in rows if r["type"] == "V"]
    out = [
        ("전체", rows),
        ("S", [r for r in rows if r["type"] == "S"]),
        ("V", V),
        ("V·화면 글자 있음", [r for r in V if r.get("overlay_text") is True]),
        ("V·화면 글자 없음", [r for r in V if r.get("overlay_text") is False]),
        ("V·화면 글자 미표시", [r for r in V if r.get("overlay_text") is None]),
    ]
    out += [(f"source={s}", [r for r in rows if r.get("source", "human") == s]) for s in query_set.SOURCES]
    out += [(f"split={s}", [r for r in rows if r.get("split") == s]) for s in query_set.SUBSETS]
    return [(name, rs) for name, rs in out if rs]


def by_key(key, seg_field="seg", iou_field="iou", top_field="top3"):
    """결과 행의 row[key] = {"seg", "iou", "top3"}에서 지표 5개를 계산하는 함수."""
    def fn(r):
        v = r.get(key) or {}
        seg = v.get(seg_field)
        if not seg:  # 결과 없음
            return 0.0, 0.0, 0.0, 0.0, 0.0
        gts = [tuple(g) for g in r["gt"]]
        x = float(v.get(iou_field) or 0.0)
        top = v.get(top_field) if top_field else None
        r3 = None if top is None else float(any(best_iou(s, gts) >= 0.3 for s in top))
        return x, float(x >= 0.3), float(x >= 0.5), r3, float(start_ok(seg, gts))
    return fn


def random_metrics(r):
    v = r["random"]
    return v["mean_iou"], v["hit30"], v["hit50"], v.get("r3"), v.get("start5")


def summarize(rows, methods):
    """methods: {이름: 행 → (평균 IoU용 IoU, hit30, hit50, r3, start5)} (None이면 그 지표 없음).
    결과: {묶음: {"n": 질의 수, 방식: {지표: 값 또는 None}}}"""
    result = {}
    for name, rs in groups(rows):
        g = {"n": len(rs)}
        for m, fn in methods.items():
            vals = [fn(r) for r in rs]
            g[m] = {}
            for i, k in enumerate(METRICS):
                col = [v[i] for v in vals]
                g[m][k] = None if any(c is None for c in col) else round(sum(col) / len(col), 4)
        result[name] = g
    return result


def format_table(summary, labels=None):
    """묶음마다 방식별 지표 표 (터미널 출력용)."""
    def pct(x):
        return "  -  " if x is None else f"{x * 100:5.1f}%"
    lines = []
    for name, g in summary.items():
        lines.append(f"[{name}] 질의 {g['n']}개")
        for m, v in g.items():
            if m == "n":
                continue
            label = (labels or {}).get(m, m)
            lines.append(f"  {label:<28} 평균 IoU {v['mean_iou']:.3f} | ≥0.3 {pct(v['hit30'])} | ≥0.5 {pct(v['hit50'])}"
                         f" | R@3 {pct(v['r3'])} | 시작±5초 {pct(v['start5'])}")
    return "\n".join(lines)
