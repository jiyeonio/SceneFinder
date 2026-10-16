"""평가셋 v2(라벨링 JSON) 실험 결과로 docs/experiments/eval_v2.md를 만듭니다.

    python ai/experiments/translation_compare/make_report_v2.py --results ~/scenefinder_eval/results_v2 \
        [--queries 결과폴더/labels_snapshot.json] [--draft AI초안.json] [--output docs/experiments/eval_v2.md]

- 결과 폴더의 results.json(run.py), fusion_results.json(fusion.py)을 읽습니다.
- --queries: 실험에 쓴 라벨 JSON (기본: 결과 폴더의 labels_snapshot.json). source·overlay_text·영상 정보를 여기서 읽습니다.
- --draft: 검수 전 AI 초안. 주면 검수한 질의 중 초안에서 바뀐 것(질의 문장·유형·정답 구간·화면 글자 표시)을 셉니다.
- '해석' 절(INTERPRETATION)은 작성자가 결과를 보고 쓴 내용입니다. 결과가 바뀌면 함께 고쳐야 합니다.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import query_set
import summary

ROOT = Path(__file__).resolve().parents[3]
METHODS = [  # (결과 파일, 행의 키, 표시 이름)
    ("run", "a", "(a) NLLB 번역 + Moment-DETR"),
    ("run", "b", "(b) opus-mt 번역 + Moment-DETR"),
    ("run", "c", "(c) 다국어 CLIP (번역 없음)"),
    ("run", "d", "(d) 자막 검색 (MiniLM, 서비스 구간 보정)"),
    ("run", "e_qwen_incl", "(e) Qwen3-VL-4B 설명문 검색 (화면 글자 포함)"),
    ("fusion", "e_M1", "(e) 설명문 검색 + 앞뒤 1칸(2초) 확장"),
    ("fusion", "A", "융합 A: 자막+설명문 하나의 목록"),
    ("fusion", "B_M0", "융합 B: 각각 검색 후 점수 max"),
    ("fusion", "B_M1", "융합 B + 설명문 앞뒤 1칸 확장"),
    ("run", "random", "무작위 기준선 (기댓값)"),
]
GROUPS = ["전체", "S", "V", "V·화면 글자 있음", "V·화면 글자 없음", "source=ai_draft", "source=human_reviewed", "source=human"]
GROUP_LABEL = {"전체": "전체", "S": "S", "V": "V", "V·화면 글자 있음": "V 글자 있음", "V·화면 글자 없음": "V 글자 없음",
               "source=ai_draft": "미검수(ai_draft)", "source=human_reviewed": "검수(human_reviewed)", "source=human": "직접 작성(human)"}

REVIEW_NOTE = ("- 검수 순서: 먼저 무작위로 고른 30개를 검수(수정 0개)했고, 나머지 60개도 검수자가 확인해 고칠 것이 없어 "
               "검수 완료로 표시했습니다.")

INTERPRETATION = """\
1. **처음 실험보다 모든 방식이 크게 낮습니다.** IoU ≥ 0.3 기준 가장 좋은 방식도 34%입니다. 영상이 1분 안팎에서 2:40~15분으로 길어져 \
후보 구간이 많아졌고, 무작위 기준선도 13%에서 3%로 떨어졌습니다. 처음 실험 수치는 짧은 영상 4개라 높게 나온 것으로 봐야 합니다.
2. **설명문 검색에 구간 확장(M1)을 붙인 방식이 가장 좋습니다.** 전체 IoU ≥ 0.3 기준 34%(31/90), IoU ≥ 0.5 기준 17%(15/90)로, \
S에서도 자막 검색(27%)보다 높습니다. 설명문 검색의 1위 구간은 2초(중앙값)인데 정답은 7초(중앙값)라, 위치가 맞아도 IoU가 낮게 나왔습니다. \
V에서 놓친 질의 중 19개는 1위 구간 중심이 정답 중심과 10초 안이었습니다. 처음 실험에서는 정답이 2~3초로 짧아 M1이 IoU ≥ 0.5를 낮췄지만, \
이번에는 두 기준 모두 올랐습니다. M1은 미리 정한 세 규칙(M0·M1·M2) 중 결과를 보고 고른 것이라, 다른 평가셋에서 한 번 더 확인해야 합니다.
3. **자막 검색(d)은 S에서도 27%(8/30)로 처음 실험(100%)보다 크게 떨어졌습니다.** 틀린 경우는 같은 내용을 다른 시점에 말한 경우(조명 이야기는 \
87초, 켜는 장면은 309초), Whisper 오인식(「고추 REALLY」, 다른 경기 해설로 인식), 말 없는 450초를 한 문장으로 합친 자막(먹방 마지막 인사)이었습니다. \
1위 자막 하나만 쓰는 지금 방식은 문장이 100~250개인 긴 영상에서 약합니다.
4. **융합 A·B는 설명문 검색 단독과 비슷합니다(18~20%).** 처음 실험처럼 자막 검색이 강하지 않아 합쳐도 크게 오르지 않았습니다. \
B에 구간 확장을 붙여도 29%로 설명문 검색 + 확장(34%)보다 낮습니다. 자막 점수가 이긴 질의에서 자막 1위가 틀린 경우가 많기 때문입니다.
5. **다국어 CLIP(c)은 IoU ≥ 0.5에서 11%로 설명문 검색(확장 전 7%)보다 높고**, 말 없는 영상 4개(27개 질의)에서 6개를 맞혀 \
설명문 검색 확장 전(1개)보다 좋았습니다(확장 후 7개). Moment-DETR(a)(b)는 1위 구간이 32초(중앙값)로 길어 7~8%에 그쳤습니다.
6. **화면 글자가 있는 V 질의에서 설명문 검색이 오히려 낮았습니다(확장 후 8/26, 글자 없음 13/34).** 다만 글자 있음 질의는 tofu_silent(7개)·airpods_fake(5개)처럼 \
화면 전체에 글자가 깔린 영상에 몰려 있어, 화면 글자의 효과와 영상의 난이도를 이 결과로는 나눌 수 없습니다.

**다음 단계:** 1위 하나가 아니라 상위 k개 안에 정답이 있는지(R@k)도 재고, 설명문 검색의 구간 길이 규칙을 따로 평가셋을 나눠 정하고, \
정답 없음 질의 12개로 점수 임계값(결과 없음 판정)을 평가하는 것이 필요합니다.
"""


def metric_fn(kind, key):
    if key == "random":
        return lambda r: (r["random"]["mean_iou"], r["random"]["hit30"], r["random"]["hit50"])
    return summary.by_iou(lambda r: (r.get(key) or {}).get("iou"))


def pct(x, n):
    return f"{x * 100:.0f}% ({round(x * n)}/{n})"


def seg(s):
    return "–" if not s else f"{s[0]:.1f}–{s[1]:.1f}"


def review_stats(labels, draft):
    """검수 통계: source별 수, 검수한 질의 중 초안에서 바뀐 수(항목별)."""
    src = Counter(q.get("source", "human") for q in labels["queries"])
    stats = {"source": dict(src), "changed": None}
    if draft:
        old = {q["num"]: q for q in draft["queries"]}
        overlay = lambda q: q["overlay_text"] if "overlay_text" in q else "화면 글자 있음" in q.get("note", "")  # noqa: E731
        changed, fields = 0, Counter()
        for q in labels["queries"]:
            if q.get("source") != "human_reviewed" or q["num"] not in old:
                continue
            p, diff = old[q["num"]], []
            if q["query"] != p["query"]:
                diff.append("질의 문장")
            if q["type"] != p["type"]:
                diff.append("유형")
            if [[float(a), float(b)] for a, b in q["gt"]] != [[float(a), float(b)] for a, b in p["gt"]]:
                diff.append("정답 구간")
            if bool(q.get("overlay_text")) != bool(overlay(p)):
                diff.append("화면 글자 표시")
            if diff:
                changed += 1
                fields.update(diff)
        stats["changed"] = {"count": changed, "fields": dict(fields),
                            "deleted": len(set(old) - {q["num"] for q in labels["queries"]})}
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, help="run.py·fusion.py의 --out 폴더")
    parser.add_argument("--queries", default=None)
    parser.add_argument("--draft", default=None, help="검수 전 AI 초안 JSON (수정 통계용)")
    parser.add_argument("--output", default=str(ROOT / "docs/experiments/eval_v2.md"))
    args = parser.parse_args()
    out = Path(args.results).expanduser()
    qpath = Path(args.queries).expanduser() if args.queries else out / "labels_snapshot.json"
    labels = json.loads(qpath.read_text(encoding="utf-8"))
    draft = json.loads(Path(args.draft).expanduser().read_text(encoding="utf-8")) if args.draft else None
    qs = query_set.load(qpath)
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    fus = json.loads((out / "fusion_results.json").read_text(encoding="utf-8"))

    # run·fusion 행을 질의 번호로 합쳐 같은 묶음 기준으로 다시 집계
    fus_rows = {r["num"]: r for r in fus["rows"]}
    rows = []
    for r in res["rows"]:
        row = summary.annotate(dict(r), qs)
        for key in ("e_M1", "A", "B_M0", "B_M1"):
            row[key] = fus_rows[r["num"]][key]
        rows.append(row)
    methods = {key: metric_fn(kind, key) for kind, key, _ in METHODS}
    sm = summary.summarize(rows, methods)
    groups = [g for g in GROUPS if g in sm]
    names = {key: label for _, key, label in METHODS}
    meta, fmeta = res["meta"], fus["meta"]
    stats = review_stats(labels, draft)

    L = ["# 평가셋 v2: 분석된 YouTube 영상 12개로 다시 잰 장면 검색 비교", "",
         "서비스에서 분석했던 YouTube 영상 12개(2:40~15:01)로 만든 평가셋으로 번역 방식별 영상 검색, 자막 검색, "
         "VLM 설명문 검색, 자막+설명문 융합을 다시 비교했습니다. 처음 실험([translation_compare.md](translation_compare.md))은 "
         "1분 안팎 영상 4개·질의 20개였고, 이번에는 말 없는 영상·긴 영상을 포함해 질의 "
         f"{len(rows)}개입니다.", "",
         "정답 구간은 AI 초안을 사람이 검수하는 방식으로 만들었습니다. 아래 「라벨과 검수」에 검수 현황이 있습니다. "
         "**미검수 초안이 남아 있으면 그 질의의 결과는 참고용입니다.**", ""]

    # ---------- 요약 ----------
    head = "| 방식 | " + " | ".join(f"{GROUP_LABEL[g]} (n={sm[g]['n']})" for g in groups) + " |"
    sep = "|---|" + "---|" * len(groups)
    L += ["## 요약", ""]
    for metric, title in (("hit30", "IoU ≥ 0.3 (1위 구간이 정답과 30% 이상 겹친 비율)"),
                          ("hit50", "IoU ≥ 0.5"), ("mean_iou", "평균 IoU")):
        L += [f"### {title}", "", head, sep]
        for _, key, label in METHODS:
            if metric == "mean_iou":
                cells = [f"{sm[g][key][metric]:.3f}" for g in groups]
            elif key == "random":  # 기댓값이라 개수 없이 비율만
                cells = [f"{sm[g][key][metric] * 100:.0f}%" for g in groups]
            else:
                cells = [pct(sm[g][key][metric], sm[g]["n"]) for g in groups]
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["- S = 말(자막)로 설명되는 장면, V = 말로는 안 나오고 화면에만 보이는 장면. "
          "V 글자 있음 = 화면에 덧씌운 글자(자막·제목·그래픽)만으로도 찾을 수 있는 장면.",
          "- 자막이 없는 영상(말소리 없음)에서 (d)는 결과가 없으므로 IoU 0으로 셉니다. 융합 A·B는 이 경우 설명문만으로 검색합니다.",
          "- 무작위 기준선은 영상마다 정답 평균 길이의 구간을 무작위 위치에 "
          f"{meta['random_samples']}번 뽑은 기댓값입니다(seed {meta['random_seed']}).",
          "- 영상에 없는 장면 질의(정답 없음) "
          f"{len(labels.get('negative_queries', []))}개는 이번 집계에 넣지 않았습니다(현재 스크립트는 1위 구간만 평가).", ""]

    L += ["### 해석", "", INTERPRETATION, ""]

    # ---------- 라벨과 검수 ----------
    src = stats["source"]
    L += ["## 라벨과 검수", "",
          f"- 질의 {len(rows)}개: " + ", ".join(f"{GROUP_LABEL['source=' + k]} {v}개" for k, v in sorted(src.items())),
          REVIEW_NOTE,
          f"- 정답 없음 질의 {len(labels.get('negative_queries', []))}개 (영상 "
          f"{len({q['video'] for q in labels.get('negative_queries', [])})}개)"]
    if stats["changed"] is not None:
        c = stats["changed"]
        detail = ", ".join(f"{k} {v}개" for k, v in c["fields"].items()) or "없음"
        L.append(f"- 검수한 {src.get('human_reviewed', 0)}개 중 AI 초안에서 바뀐 질의 {c['count']}개 (항목별: {detail}), "
                 f"초안에서 삭제된 질의 {c['deleted']}개")
    L += ["- 초안 작성: 2~3초 간격 프레임과 서비스의 Whisper 자막을 보고 질의·정답 구간을 만들고, 경계는 ffmpeg로 뽑은 프레임으로 맞춤. "
          "V 질의를 만들 때 VLM 설명문은 보지 않음.",
          "- 화면 글자 표시(overlay_text): " + ", ".join(
              f"{t} {sum(1 for r in rows if r['type'] == t and r.get('overlay_text'))}/{sum(1 for r in rows if r['type'] == t)}개"
              for t in ("S", "V")), ""]

    # ---------- 영상 ----------
    L += ["## 영상", "", "| 영상 | YouTube ID | 길이 | 분야 | 자막 문장 수 | S | V | 정답 없음 |", "|---|---|---|---|---|---|---|---|"]
    neg = Counter(q["video"] for q in labels.get("negative_queries", []))
    for key in qs.video_keys:
        v = labels["videos"][key]
        dur = meta["durations"][key]
        n_s = sum(1 for r in rows if r["video"] == key and r["type"] == "S")
        n_v = sum(1 for r in rows if r["video"] == key and r["type"] == "V")
        L.append(f"| {key} | `{v.get('youtube_id', '')}` | {int(dur // 60)}:{int(dur % 60):02d} | {v.get('domain', '')} | "
                 f"{meta['subtitle_segments'][key]} | {n_s} | {n_v} | {neg.get(key, 0)} |")
    L.append("")

    # ---------- 영상별 IoU ≥ 0.3 ----------
    L += ["### 영상별 IoU ≥ 0.3", "", "| 영상 | 질의 | " + " | ".join(names[k] for k in ("c", "d", "e_qwen_incl", "e_M1", "A")) + " |",
          "|---|---|" + "---|" * 5]
    for key in qs.video_keys:
        rs = [r for r in rows if r["video"] == key]
        cells = [f"{sum(methods[k](r)[1] for r in rs):.0f}/{len(rs)}" for k in ("c", "d", "e_qwen_incl", "e_M1", "A")]
        L.append(f"| {key} | {len(rs)} | " + " | ".join(cells) + " |")
    L.append("")

    # ---------- 설정 ----------
    cap = meta.get("captions", {}).get("qwen_incl", {})
    L += ["## 실험 설정", "",
          "- 질의·정답: `" + Path(qs.source).name + "` (실험 시작 때 라벨 파일을 결과 폴더에 복사한 것)",
          f"- (a) `{meta['nllb']}` 번역 / (b) `{meta['opus']}` 번역 → Moment-DETR 1위 구간 (CLIP ViT-B/32, 2초 단위 feature)",
          f"- (c) `{meta['mclip']}`: 한국어 질의와 2초 단위 프레임 feature를 직접 비교",
          f"- (d) Whisper `{meta['whisper']}` 자막 + fine-tuned MiniLM 1위 자막 구간, 서비스 구간 보정(시작 {meta['subtitle_pad_before']}초 앞당김, 최소 {meta['subtitle_min_len']}초)",
          f"- (e) `{cap.get('model', 'Qwen/Qwen3-VL-4B-Instruct')}`, 2초마다 가운데 프레임 1장을 화면 글자 포함 프롬프트로 설명 → 같은 MiniLM으로 검색",
          f"- 융합 A·B와 설명문 구간 확장(M1, 1위 설명문 창의 앞뒤 2초씩): [translation_compare.md](translation_compare.md)의 「(d)+(e) 실제 융합」과 같은 방식. M1은 처음 실험 전에 정한 규칙이고 이번 데이터에 맞춰 바꾸지 않음",
          f"- (d) 재현 확인: fusion.py에서 다시 계산한 (d) 1위 구간이 run.py와 다른 질의 {fmeta.get('d_reproduction_mismatches')}/{fmeta.get('d_reproduction_checked')}개",
          f"- 환경: {meta['gpu']}"]
    if cap.get("single"):
        frames = sum(v["frames"] for v in cap["single"].values())
        secs = sum(v["total_sec"] for v in cap["single"].values())
        L.append(f"- (e) 설명문 생성: {frames}장, {secs / 60:.0f}분 (장당 {secs / frames:.2f}초, 1장씩 처리)")
    L.append("")

    # ---------- 질의별 ----------
    L += ["## 질의별 결과", "", "1위 구간(초)과 IoU. ✓ = IoU ≥ 0.3. 글자 = 화면 글자로 찾을 수 있음.", "",
          "| # | 영상 | 유형 | 출처 | 질의 | 정답 | (a) | (c) | (d) | (e) | A |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    short = {"ai_draft": "초안", "human_reviewed": "검수", "human": "직접"}
    for r in rows:
        def cell(k):
            v = r.get(k)
            if not v or not v.get("seg"):
                return "–"
            return f"{seg(v['seg'])} ({v['iou']:.2f}){' ✓' if v['iou'] >= 0.3 else ''}"
        typ = r["type"] + (" 글자" if r.get("overlay_text") else "")
        gt = ", ".join(seg(g) for g in r["gt"])
        L.append(f"| {r['num']} | {r['video']} | {typ} | {short.get(r['source'], r['source'])} | {r['query']} | {gt} | "
                 + " | ".join(cell(k) for k in ("a", "c", "d", "e_qwen_incl", "A")) + " |")
    L.append("")

    # ---------- 재현·한계 ----------
    L += ["## 재현 방법", "", "프로젝트 루트에서, 영상 12개를 `~/scenefinder_eval/videos/<YouTube ID>.mp4`에 둔 상태로 실행합니다.", "",
          "    OUT=~/scenefinder_eval/results_v2",
          "    cp ~/scenefinder_eval/labels_draft.json $OUT/labels_snapshot.json",
          "    python ai/experiments/translation_compare/captions.py --out $OUT --queries $OUT/labels_snapshot.json --variants qwen_incl --skip-batch-timing",
          "    python ai/experiments/translation_compare/run.py --out $OUT --queries $OUT/labels_snapshot.json",
          "    python ai/experiments/translation_compare/fusion.py --out $OUT",
          "    python ai/experiments/translation_compare/make_report_v2.py --results $OUT --draft <검수 전 AI 초안.json>", "",
          "- 영상·feature·설명문·결과 JSON은 저장소 밖(`~/scenefinder_eval/`)에 둡니다.",
          "- 라벨만 바뀌었으면 captions.py는 다시 돌릴 필요가 없습니다(feature·자막·설명문은 결과 폴더에 캐시됨).", "",
          "## 한계", "",
          "- 질의 수가 늘었지만 묶음별로는 아직 수십 개라, 몇 %p 차이는 우연일 수 있습니다.",
          "- 정답 구간은 AI 초안 기반이고 일부는 미검수입니다. 정답 경계는 프레임 기준 대략값입니다.",
          "- 서비스 Whisper 자막이 크게 틀린 영상이 있습니다(다른 경기 해설로 인식, 없는 말 생성, 450초를 한 문장으로 합침). (d)와 융합 결과에 영향을 줍니다.",
          "- 화면에 자막이 박힌 영상이 많아, 말 없는 영상도 (e)가 화면 글자를 읽어 찾을 수 있습니다. V를 화면 글자 유무로 나눈 이유입니다.",
          "- 피아노 영상은 구별되는 장면이 적어 질의가 3개뿐입니다.", ""]

    Path(args.output).write_text("\n".join(L), encoding="utf-8")
    print("작성:", args.output)


if __name__ == "__main__":
    main()
