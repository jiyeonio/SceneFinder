"""run.py·fusion.py 결과를 질의 묶음별로 집계합니다.

묶음: 전체 / S / V / V·화면 글자 있음 / V·화면 글자 없음 / V·화면 글자 미표시 / source별(ai_draft·human_reviewed·human)
      / split별(dev·test, eval_youtube_videos.tsv에 있는 영상만)
지표: 평균 IoU, IoU ≥ 0.3 비율, IoU ≥ 0.5 비율. 결과가 없는 방식(예: 자막 없는 영상의 (d))은 IoU 0으로 셉니다.
"""
import query_set


def annotate(row, qs):
    """결과 행에 질의의 source·overlay_text를 붙임."""
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


def summarize(rows, methods):
    """methods: {이름: 행 → (IoU, IoU≥0.3 여부/확률, IoU≥0.5 여부/확률)}.
    결과: {묶음: {"n": 질의 수, 방식: {"mean_iou", "hit30", "hit50"}}}"""
    result = {}
    for name, rs in groups(rows):
        g = {"n": len(rs)}
        for m, fn in methods.items():
            vals = [fn(r) for r in rs]
            g[m] = {k: round(sum(v[i] for v in vals) / len(vals), 4)
                    for i, k in enumerate(("mean_iou", "hit30", "hit50"))}
        result[name] = g
    return result


def by_iou(get):
    """행에서 IoU를 꺼내는 함수 → 지표 함수. get이 None을 돌려주면 IoU 0."""
    def fn(r):
        v = get(r)
        v = 0.0 if v is None else float(v)
        return v, float(v >= 0.3), float(v >= 0.5)
    return fn


def format_table(summary, labels=None):
    """묶음마다 방식별 '평균 IoU / IoU≥0.3 / IoU≥0.5' 표 (터미널 출력용)."""
    lines = []
    for name, g in summary.items():
        lines.append(f"[{name}] 질의 {g['n']}개")
        for m, v in g.items():
            if m == "n":
                continue
            label = (labels or {}).get(m, m)
            lines.append(f"  {label:<28} 평균 IoU {v['mean_iou']:.3f} | ≥0.3 {v['hit30'] * 100:5.1f}% | ≥0.5 {v['hit50'] * 100:5.1f}%")
    return "\n".join(lines)
