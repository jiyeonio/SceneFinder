"""평가셋 v2(라벨링 JSON) 실험 결과로 docs/experiments/eval_v2.md를 만듭니다.

    python ai/experiments/translation_compare/make_report_v2.py --results ~/scenefinder_eval/results_v2 \
        [--queries 결과폴더/labels_snapshot.json] [--draft AI초안.json] [--output docs/experiments/eval_v2.md]

- 결과 폴더의 results.json(run.py), fusion_results.json(fusion.py)을 읽습니다.
- --queries: 실험에 쓴 라벨 JSON (기본: 결과 폴더의 labels_snapshot.json). source·overlay_text·영상 정보를 여기서 읽습니다.
- --draft: 검수 전 AI 초안. 주면 검수한 질의 중 초안에서 바뀐 것(질의 문장·유형·정답 구간·화면 글자 표시)을 셉니다.
- --whisper-compare: 같은 라벨로 Whisper 모델만 바꿔 돌린 결과 폴더. 주면 (d)·융합 결과를 비교하는 절을 넣습니다.
- --s-kinds: S 질의를 '말 내용'/'화면 묘사'로 나눈 TSV (기본 docs/experiments/eval_v2_s_query_kinds.tsv).
- dev/test 나누기는 docs/experiments/eval_youtube_videos.tsv의 split 열을 씁니다.
- '해석' 절(INTERPRETATION)은 작성자가 결과를 보고 쓴 내용입니다. 결과가 바뀌면 함께 고쳐야 합니다.
"""
import argparse
import csv
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
    ("fusion", "e_M1", "(e) 설명문 검색 + 앞뒤 2초 확장 (M1, 탐색적)"),
    ("fusion", "A", "융합 A: 자막+설명문 하나의 목록"),
    ("fusion", "B_M0", "융합 B: 각각 검색 후 점수 max"),
    ("fusion", "B_M1", "융합 B + 설명문 앞뒤 2초 확장 (M1, 탐색적)"),
    ("run", "random", "무작위 기준선 (기댓값)"),
]
GROUPS = ["전체", "S", "V", "V·화면 글자 있음", "V·화면 글자 없음", "source=ai_draft", "source=human_reviewed", "source=human"]
GROUP_LABEL = {"전체": "전체", "S": "S", "V": "V", "V·화면 글자 있음": "V 글자 있음", "V·화면 글자 없음": "V 글자 없음",
               "source=ai_draft": "미검수(ai_draft)", "source=human_reviewed": "검수(human_reviewed)", "source=human": "직접 작성(human)"}

EXPLORATORY_NOTE = ("- **(M1, 탐색적)** 표시가 붙은 두 방식(설명문 1위 구간을 앞뒤 2초씩 넓힘)은 이 평가셋 결과를 본 뒤 "
                    "추가로 계산한 것입니다. 규칙 자체는 처음 실험 때 정했지만, 이번 보고에 넣을지는 결과를 보고 정했으므로 "
                    "다른 방식과 같은 조건의 비교가 아닙니다. 앞으로는 dev에서 정하고 test에서 확인해야 합니다(아래 「dev/test 나누기」).")
KEY_METHODS = ["c", "d", "e_qwen_incl", "e_M1", "A", "B_M0", "random"]
S_KIND_CRITERIA = [
    "- **말 내용**: 찾는 대상이 말한 내용·말하는 행위(설명, 주장, 소개, 인사, 특정 발언)인 질의. 소리만 들어도 정답 구간을 고를 수 있다. "
    "예: 「배터리 수명 늘리는 방법 설명」, 「잘 먹었다고 인사하는 장면」",
    "- **화면 묘사**: 찾는 대상이 보이는 물체·동작·화면 그래픽·경기 장면인 질의. 소리를 끄고 봐도 정답 구간을 고를 수 있다. "
    "예: 「이어팁 크기 비교하는 장면」, 「러그 까는 장면」",
    "- 둘 다 해당하면 질의의 핵심 동사로 정함: 말하다·설명하다·소개하다·인사하다 → 말 내용, 그 밖의 동작·물체 → 화면 묘사.",
    "- 분류는 질의 문장만 보고 했고(결과를 보기 전 기준), 질의별 분류와 이유는 "
    "[eval_v2_s_query_kinds.tsv](eval_v2_s_query_kinds.tsv)에 있습니다.",
]

REVIEW_NOTE = ("- 검수 순서: 먼저 무작위로 고른 30개를 검수(수정 0개)했고, 나머지 60개도 검수자가 확인해 고칠 것이 없어 "
               "검수 완료로 표시했습니다.")

INTERPRETATION_WHISPER = """\
**해석 (작성자 판단)**

1. **large-v3-turbo로 바꾸면 S 질의의 자막 검색이 IoU ≥ 0.3 기준 27%(8/30) → 43%(13/30)로 오릅니다.** dev(5 → 7/14)와 \
test(3 → 6/16) 모두 올라, 한쪽 영상에만 맞춘 결과는 아닙니다. 새로 맞힌 6개의 원인은 섞여 있습니다. small의 오인식이나 누락 \
(「소음을 상쇄」를 「상세」로 받아씀, 선수 교체 해설이 자막에 없음)도 있고, 같은 문장이 small에도 있었지만 문장 경계·시간이 달라 \
다른 창이 1위가 된 경우(「기기라는 메뉴가 있을 거예요」)도 있습니다.
2. **새로 틀린 질의도 있습니다.** wc_goals의 프리킥 골은 turbo가 해설 구간을 「라이터.」 같은 짧은 오인식으로 만들어 1위를 놓쳤습니다. \
경기 해설처럼 함성·잡음이 큰 영상은 두 모델 모두 불안정합니다.
3. **융합도 함께 오릅니다(S 기준 A 27% → 40%, B 30% → 47%).** V에서는 (d)·B가 그대로이고 A만 13% → 18%로, \
자막 품질 개선의 효과는 주로 말로 설명되는 장면에 나타납니다.
4. 이 비교는 dev/test를 나누기 전에 12개 전체로 한 것입니다. 서비스 기본 모델을 바꿀지는 처리 시간·GPU 메모리와 함께 dev에서 다시 확인한 뒤 정하는 것이 맞습니다.
"""

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

7. **R@3·시작점 오차로 보면 '위치는 맞는데 1위·구간 길이가 틀린' 경우가 많습니다.** 설명문 검색(e)은 1위 IoU ≥ 0.3이 18%지만 \
R@3은 40%, 시작 ±5초는 33%입니다. 자막 검색(d)도 S에서 1위 27% → R@3 50%로, 맞는 자막이 2~3위에 있는 경우가 많았습니다. \
순위를 다시 매기거나(re-ranking) 상위 후보를 함께 보여주는 화면이 1위 정확도를 올리는 것보다 효과가 클 수 있습니다. \
번역 + Moment-DETR(a)(b)는 R@3도 12~17%로, 후보를 늘려도 낮습니다.
8. 이 두 지표는 결과를 본 뒤 추가한 것이 아니라 요청에 따라 정의를 먼저 정하고(중복 후보 제외 기준 IoU 0.5, 시작 허용 ±5초) 계산했습니다. \
다만 (M1, 탐색적) 방식의 R@3·시작점 값도 같은 이유로 탐색적 결과입니다.

**다음 단계:** (1) 설명문 구간 길이 규칙(M1 등)·재순위·Whisper 모델은 dev에서만 비교해 정하고 test로 확인, \
(2) 말 내용을 찾는 S 질의를 dev·test에 10개 이상씩 추가, (3) 정답 없음 질의 12개로 점수 임계값(결과 없음 판정) 평가.
"""


def metric_fn(kind, key):
    return summary.random_metrics if key == "random" else summary.by_key(key)


def pct(x, n):
    return "–" if x is None else f"{x * 100:.0f}% ({round(x * n)}/{n})"


def p0(x):
    return "–" if x is None else f"{x * 100:.0f}%"


def seg(s):
    return "–" if not s else f"{s[0]:.1f}–{s[1]:.1f}"


def cell3(v):
    """IoU≥0.3 / IoU≥0.5 / 평균 IoU를 한 칸에."""
    return f"{v['hit30'] * 100:.0f}% / {v['hit50'] * 100:.0f}% / {v['mean_iou']:.3f}"


def read_tsv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def merged_rows(out, qs):
    """run·fusion 행을 질의 번호로 합침."""
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    fus = json.loads((out / "fusion_results.json").read_text(encoding="utf-8"))
    fus_rows = {r["num"]: r for r in fus["rows"]}
    rows = []
    for r in res["rows"]:
        row = summary.annotate(dict(r), qs)
        for key in ("e_M1", "A", "B_M0", "B_M1"):
            row[key] = fus_rows[r["num"]][key]
        rows.append(row)
    return res, fus, rows


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
    parser.add_argument("--whisper-compare", default=None, help="Whisper 모델만 바꿔 돌린 결과 폴더")
    parser.add_argument("--s-kinds", default=str(ROOT / "docs/experiments/eval_v2_s_query_kinds.tsv"))
    args = parser.parse_args()
    out = Path(args.results).expanduser()
    qpath = Path(args.queries).expanduser() if args.queries else out / "labels_snapshot.json"
    labels = json.loads(qpath.read_text(encoding="utf-8"))
    draft = json.loads(Path(args.draft).expanduser().read_text(encoding="utf-8")) if args.draft else None
    qs = query_set.load(qpath)
    # run·fusion 행을 질의 번호로 합쳐 같은 묶음 기준으로 다시 집계
    res, fus, rows = merged_rows(out, qs)
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
    L += ["## 요약", "",
          "각 묶음의 세 칸: **IoU ≥ 0.3 / IoU ≥ 0.5 / 평균 IoU** (1위 구간), **R@3** (상위 3개 중 하나라도 IoU ≥ 0.3), "
          "**시작 ±5초** (1위 구간 시작이 정답 시작 ±5초 안).", "",
          "| 방식 | " + " | ".join(f"{g} (n={sm[g]['n']}) | {g} R@3 | {g} 시작 ±5초" for g in ("전체", "S", "V")) + " |",
          "|---|" + "---|" * 9]
    for _, key, label in METHODS:
        L.append(f"| {label} | " + " | ".join(f"{cell3(sm[g][key])} | {p0(sm[g][key]['r3'])} | {p0(sm[g][key]['start5'])}"
                                              for g in ("전체", "S", "V")) + " |")
    L += ["", "- R@3 후보는 각 방식의 순위대로 뽑되, 앞 순위 후보와 IoU ≥ 0.5로 겹치는 후보는 같은 위치로 보고 건너뛴 상위 3개입니다"
          "(자막·설명문은 1~3문장 묶음 창이 겹쳐 나오므로). 자막 검색은 서비스 구간 보정을 적용한 구간, 융합 B는 자막·설명문 후보를 점수순으로 합친 순위입니다.",
          "- 시작점 오차는 정답 구간이 여러 개면 가장 가까운 정답의 시작과 비교합니다. 결과가 없는 경우(말 없는 영상의 (d))는 0으로 셉니다.",
          "- 무작위 기준선의 R@3·시작 ±5초는 정답 평균 길이 구간을 무작위로 3개(시작점은 1개) 뽑은 기댓값입니다."]
    L += ["", EXPLORATORY_NOTE, "", "아래는 묶음별 세부 표입니다.", ""]
    for metric, title in (("hit30", "IoU ≥ 0.3 (1위 구간이 정답과 30% 이상 겹친 비율)"),
                          ("hit50", "IoU ≥ 0.5"), ("mean_iou", "평균 IoU"),
                          ("r3", "R@3 (상위 3개 중 하나라도 IoU ≥ 0.3)"), ("start5", "시작점 오차 ±5초 이내")):
        L += [f"### {title}", "", head, sep]
        for _, key, label in METHODS:
            if metric == "mean_iou":
                cells = [f"{sm[g][key][metric]:.3f}" for g in groups]
            elif key == "random":  # 기댓값이라 개수 없이 비율만
                cells = [p0(sm[g][key][metric]) for g in groups]
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

    # ---------- 영상별 결과 ----------
    vid_methods = ["c", "d", "e_qwen_incl", "e_M1", "A", "B_M0"]
    short_name = {"c": "(c) 다국어 CLIP", "d": "(d) 자막", "e_qwen_incl": "(e) 설명문", "e_M1": "(e)+M1 확장",
                  "A": "융합 A", "B_M0": "융합 B"}
    L += ["### 영상별 결과", "", "각 칸: IoU ≥ 0.3 개수 / IoU ≥ 0.5 개수 / 평균 IoU. 말 양은 자막의 분당 글자 수 기준(많음·중간·없음).", "",
          "| 영상 | split | 말 양 | 질의 (S/V) | " + " | ".join(short_name[k] for k in vid_methods) + " |",
          "|---|---|---|---|" + "---|" * len(vid_methods)]
    tsv = {r["key"]: r for r in read_tsv(query_set.SPLIT_FILE)}
    for key in qs.video_keys:
        rs = [r for r in rows if r["video"] == key]
        n_s = sum(r["type"] == "S" for r in rs)
        cells = []
        for k in vid_methods:
            vals = [methods[k](r) for r in rs]
            cells.append(f"{sum(v[1] for v in vals):.0f} / {sum(v[2] for v in vals):.0f} / {sum(v[0] for v in vals) / len(vals):.2f}")
        t = tsv.get(key, {})
        L.append(f"| {key} | {t.get('split', '')} | {t.get('speech', '')} | {len(rs)} ({n_s}/{len(rs) - n_s}) | " + " | ".join(cells) + " |")
    L.append("")

    # ---------- S 질의: 말 내용 vs 화면 묘사 ----------
    kinds_path = Path(args.s_kinds)
    if kinds_path.exists():
        kinds = {int(r["num"]): r["kind"] for r in read_tsv(kinds_path)}
        S_rows = [r for r in rows if r["type"] == "S"]
        L += ["## S 질의 편향 점검: 말 내용 vs 화면 묘사", "",
              "S 질의(말로 설명되는 장면)가 실제로는 화면을 묘사하는 말투로 쓰였다면, 자막 검색(d)이 불리하고 설명문 검색(e)이 유리하게 "
              "측정될 수 있습니다. 그래서 S 질의를 두 종류로 나눠 비교했습니다.", "", "분류 기준:", ""] + S_KIND_CRITERIA + ["",
              "| 종류 | 질의 수 | (d) 자막 | (e) 설명문 | (e)+M1 확장 (탐색적) | 융합 A |", "|---|---|---|---|---|---|"]
        for kind in ("말 내용", "화면 묘사"):
            rs = [r for r in S_rows if kinds.get(r["num"]) == kind]
            if not rs:
                continue
            def agg(k):
                vals = [methods[k](r) for r in rs]
                return f"{sum(v[1] for v in vals):.0f}/{len(rs)} · {sum(v[2] for v in vals):.0f}/{len(rs)} · {sum(v[0] for v in vals) / len(rs):.2f}"
            L.append(f"| {kind} | {len(rs)} | " + " | ".join(agg(k) for k in ("d", "e_qwen_incl", "e_M1", "A")) + " |")
        n_speech = sum(1 for r in S_rows if kinds.get(r["num"]) == "말 내용")
        vis = [r for r in S_rows if kinds.get(r["num"]) == "화면 묘사"]
        hit = lambda k: int(sum(methods[k](r)[1] for r in vis))  # noqa: E731
        L += ["", "각 칸: IoU ≥ 0.3 개수 · IoU ≥ 0.5 개수 · 평균 IoU.", "",
              f"- **S 질의 {len(S_rows)}개 중 {n_speech}개만 말 내용 질의입니다.** AI 초안 작성 지침이 S를 '말과 화면이 함께 나오는 장면'으로 "
              "정의하고 장면 묘사형 예시를 줬기 때문입니다. 지금 S 결과는 사실상 '말이 함께 나오는 장면을 화면 묘사로 찾기'의 결과입니다.",
              f"- 화면 묘사 S {len(vis)}개에서도 자막 검색(d)은 IoU ≥ 0.3 기준 {hit('d')}개로 설명문 검색(e) {hit('e_qwen_incl')}개와 "
              "비슷했습니다. 즉 이번 데이터로는 '질의 말투가 자막 검색을 불리하게 만들었다'는 것도, 그 반대도 확인되지 않습니다.",
              f"- 말 내용 질의가 {n_speech}개뿐이라 두 종류의 차이는 판단할 수 없습니다. 자막 검색이 실제로 강할 것으로 보이는 "
              "말 내용 질의(설명·주장·팁·특정 발언을 찾는 질의)를 dev·test에 각각 10개 이상 추가해야 합니다.", ""]

    # ---------- dev/test ----------
    L += ["## dev/test 나누기", "",
          "과적합을 막기 위해 영상 12개를 dev 6개 / test 6개로 나눴습니다. **앞으로 구간 규칙·점수 임계값·융합 가중치 같은 설정은 "
          "dev 결과만 보고 정하고, test는 최종 보고에만 씁니다.** 실험 스크립트는 `--subset dev|test`로 해당 영상의 질의만 돌립니다.", "",
          "| split | 영상 | 질의 (S/V/V 글자 있음) | 말 많음/중간/없음 |", "|---|---|---|---|"]
    for sp in ("dev", "test"):
        keys = [k for k in qs.video_keys if tsv.get(k, {}).get("split") == sp]
        rs = [r for r in rows if r["video"] in keys]
        n_s = sum(r["type"] == "S" for r in rs)
        n_vo = sum(r["type"] == "V" and bool(r.get("overlay_text")) for r in rs)
        sp_cnt = Counter(tsv[k].get("speech", "") for k in keys)
        L.append(f"| {sp} | {', '.join(keys)} | {len(rs)} ({n_s}/{len(rs) - n_s}/{n_vo}) | "
                 f"{sp_cnt.get('많음', 0)}/{sp_cnt.get('중간', 0)}/{sp_cnt.get('없음', 0) + sp_cnt.get('거의 없음', 0)} |")
    L += ["", "나눈 기준 (결과 수치는 보지 않고 영상 정보만으로 정함):", "",
          "- 분야: 양쪽 모두 요리·리뷰·스포츠가 있고, 브이로그·먹방은 dev, 강의·음악은 test",
          "- 말 양: 말 많은 영상 2개씩, 말 없는(거의 없는) 영상은 dev 3 / test 2",
          "- 길이: 15분 가까운 영상을 한쪽에 몰지 않음 (steak_camp dev, battery_lecture test)",
          "- 질의 구성: S/V 수와 화면 글자 V 수가 비슷하게, Whisper 자막이 크게 틀린 영상도 2개씩",
          "- 이 문서의 수치는 나누기 전에 12개 전체로 낸 것이라 test도 이미 한 번 본 상태입니다. 이후 설정 변경은 dev에서만 비교합니다.", ""]

    # ---------- Whisper 비교 ----------
    if args.whisper_compare:
        wout = Path(args.whisper_compare).expanduser()
        wres, wfus, wrows = merged_rows(wout, qs)
        wsm = summary.summarize(wrows, methods)
        wname, bname = wres["meta"]["whisper"], meta["whisper"]
        L += [f"## Whisper {bname} → {wname}: 자막 검색(d) 비교", "",
              f"같은 라벨·같은 CLIP feature·같은 설명문으로 Whisper 모델만 `{bname}`에서 `{wname}`로 바꿔 자막을 다시 만들고 "
              "(d)와 융합을 다시 계산했습니다. 각 칸: IoU ≥ 0.3 / IoU ≥ 0.5 / 평균 IoU.", "",
              f"| 방식 | 묶음 | {bname} | {wname} |", "|---|---|---|---|"]
        for k in ("d", "A", "B_M0"):
            for g in ("S", "V", "전체"):
                L.append(f"| {names[k]} | {g} (n={sm[g]['n']}) | {cell3(sm[g][k])} | {cell3(wsm[g][k])} |")
        # 설정 선택이므로 dev/test를 따로 보여 줌
        L += ["", f"dev/test별 (d) 자막 검색, S 질의 (IoU ≥ 0.3 개수 / IoU ≥ 0.5 개수):", "",
              f"| split | S 질의 | {bname} | {wname} |", "|---|---|---|---|"]
        for sp in ("dev", "test"):
            xs = [r for r in rows if r.get("split") == sp and r["type"] == "S"]
            ys = [r for r in wrows if r.get("split") == sp and r["type"] == "S"]
            f = methods["d"]
            L.append(f"| {sp} | {len(xs)} | {sum(f(r)[1] for r in xs):.0f} / {sum(f(r)[2] for r in xs):.0f} | "
                     f"{sum(f(r)[1] for r in ys):.0f} / {sum(f(r)[2] for r in ys):.0f} |")
        kinds_ok = kinds_path.exists()
        L += ["", f"| 영상 | 자막 문장 수 ({bname} → {wname}) | S 질의 | (d) S IoU ≥ 0.3 ({bname} → {wname}) |", "|---|---|---|---|"]
        for key in qs.video_keys:
            rs = [r for r in rows if r["video"] == key and r["type"] == "S"]
            wr = [r for r in wrows if r["video"] == key and r["type"] == "S"]
            a = sum(methods["d"](r)[1] for r in rs); b = sum(methods["d"](r)[1] for r in wr)
            L.append(f"| {key} | {meta['subtitle_segments'][key]} → {wres['meta']['subtitle_segments'][key]} | {len(rs)} | "
                     f"{a:.0f} → {b:.0f} |" if rs else
                     f"| {key} | {meta['subtitle_segments'][key]} → {wres['meta']['subtitle_segments'][key]} | 0 | – |")
        changed = [(r, w) for r, w in zip(rows, wrows) if r["type"] == "S" and abs(methods["d"](r)[0] - methods["d"](w)[0]) > 1e-6]
        L += ["", f"- S 질의 중 (d) 1위 구간이 바뀐 질의 {len(changed)}개. "
              f"IoU ≥ 0.3 기준으로 새로 맞힌 질의 {sum(1 for r, w in changed if methods['d'](w)[1] > methods['d'](r)[1])}개, "
              f"새로 틀린 질의 {sum(1 for r, w in changed if methods['d'](w)[1] < methods['d'](r)[1])}개", ""]
        L += [INTERPRETATION_WHISPER, ""]

    # ---------- 설정 ----------
    cap = meta.get("captions", {}).get("qwen_incl", {})
    L += ["## 실험 설정", "",
          "- 질의·정답: `" + Path(qs.source).name + "` (실험 시작 때 라벨 파일을 결과 폴더에 복사한 것)",
          f"- (a) `{meta['nllb']}` 번역 / (b) `{meta['opus']}` 번역 → Moment-DETR 1위 구간 (CLIP ViT-B/32, 2초 단위 feature)",
          f"- (c) `{meta['mclip']}`: 한국어 질의와 2초 단위 프레임 feature를 직접 비교",
          f"- (d) Whisper `{meta['whisper']}` 자막 + fine-tuned MiniLM 1위 자막 구간, 서비스 구간 보정(시작 {meta['subtitle_pad_before']}초 앞당김, 최소 {meta['subtitle_min_len']}초)",
          f"- (e) `{cap.get('model', 'Qwen/Qwen3-VL-4B-Instruct')}`, 2초마다 가운데 프레임 1장을 화면 글자 포함 프롬프트로 설명 → 같은 MiniLM으로 검색",
          f"- 융합 A·B와 설명문 구간 확장(M1, 1위 설명문 창의 앞뒤 2초씩): [translation_compare.md](translation_compare.md)의 「(d)+(e) 실제 융합」과 같은 방식. "
          "M1 규칙은 처음 실험 때 정한 것이고 이번 데이터에 맞춰 바꾸지 않았지만, 이 문서에 넣은 것은 결과를 본 뒤의 결정이라 탐색적 결과로 표시",
          f"- (d) 재현 확인: fusion.py에서 다시 계산한 (d) 1위 구간이 run.py와 다른 질의 {fmeta.get('d_reproduction_mismatches')}/{fmeta.get('d_reproduction_checked')}개",
          f"- 환경: {meta['gpu']}"]
    timing = cap.get("single") if cap.get("result_batch_size", 1) == 1 else cap.get("batch")
    if timing:
        timing = {k: v for k, v in timing.items() if k != "peak_gpu_gib"}
        frames = sum(v["frames"] for v in timing.values())
        secs = sum(v["total_sec"] for v in timing.values())
        bs = cap.get("result_batch_size", 1)
        L.append(f"- (e) 설명문 생성: {frames}장, {secs / 60:.0f}분 (장당 {secs / frames:.2f}초, "
                 + ("1장씩 처리" if bs == 1 else f"{bs}장 묶음 처리") + ")")
    L.append("- 앞으로 설명문은 8장 묶음 처리로 만듭니다(captions.py 기본값). 1장씩 처리와 글자 단위로 조금 달라(tofu_silent 80장 중 "
             "31장만 완전히 같음, 평균 글자 유사도 0.86) 이 문서의 (e) 수치를 그대로 재현하려면 `--batch-size 1`이 필요합니다.")
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
          "    python ai/experiments/translation_compare/captions.py --out $OUT --queries $OUT/labels_snapshot.json --variants qwen_incl --batch-size 1 --skip-batch-timing",
          "    python ai/experiments/translation_compare/run.py --out $OUT --queries $OUT/labels_snapshot.json",
          "    python ai/experiments/translation_compare/fusion.py --out $OUT",
          "",
          "    # Whisper 비교: feature·설명문은 복사하고 자막만 large-v3-turbo로 다시 만듦",
          "    W=~/scenefinder_eval/results_v2_whisper_turbo; mkdir -p $W",
          "    cp $OUT/bench_*_clip_features.pt $OUT/captions_qwen_incl.json $OUT/labels_snapshot.json $W/",
          "    WHISPER_MODEL_SIZE=large-v3-turbo python ai/experiments/translation_compare/run.py --out $W --queries $W/labels_snapshot.json",
          "    WHISPER_MODEL_SIZE=large-v3-turbo python ai/experiments/translation_compare/fusion.py --out $W",
          "",
          "    python ai/experiments/translation_compare/make_report_v2.py --results $OUT --draft <검수 전 AI 초안.json> --whisper-compare $W", "",
          "- 영상·feature·설명문·결과 JSON은 저장소 밖(`~/scenefinder_eval/`)에 둡니다.",
          "- 라벨만 바뀌었으면 captions.py는 다시 돌릴 필요가 없습니다(feature·자막·설명문은 결과 폴더에 캐시됨).", "",
          "## 한계", "",
          "- 질의 수가 늘었지만 묶음별로는 아직 수십 개라, 몇 %p 차이는 우연일 수 있습니다.",
          "- 정답 구간은 AI 초안을 사람이 검수한 것이고(수정 0개), 경계는 프레임 기준 대략값입니다.",
          "- S 질의 대부분이 화면 묘사 말투라 자막 검색에 불리합니다(「S 질의 편향 점검」).",
          "- (M1, 탐색적) 결과는 결과를 본 뒤 추가한 것이라 같은 조건의 비교가 아닙니다.",
          "- 서비스 Whisper 자막이 크게 틀린 영상이 있습니다(다른 경기 해설로 인식, 없는 말 생성, 450초를 한 문장으로 합침). (d)와 융합 결과에 영향을 줍니다.",
          "- 화면에 자막이 박힌 영상이 많아, 말 없는 영상도 (e)가 화면 글자를 읽어 찾을 수 있습니다. V를 화면 글자 유무로 나눈 이유입니다.",
          "- 피아노 영상은 구별되는 장면이 적어 질의가 3개뿐입니다.", ""]

    Path(args.output).write_text("\n".join(L), encoding="utf-8")
    print("작성:", args.output)


if __name__ == "__main__":
    main()
