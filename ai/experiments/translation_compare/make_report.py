"""run.py 결과(results.json)로 docs/experiments/translation_compare.md를 만듭니다.

    python ai/experiments/translation_compare/make_report.py [--results 결과.json] [--output 문서.md]

'해석' 절은 작성자가 결과를 보고 쓴 내용입니다. 실험 결과가 바뀌면 함께 고쳐야 합니다.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from queries import TRANSLATION_QUALITY, VIDEO_NAMES

ROOT = Path(__file__).resolve().parents[3]
MARK = {"ok": "✅", "part": "⚠️", "bad": "❌"}
METHODS = {
    "a": "(a) NLLB 번역 + Moment-DETR",
    "b": "(b) opus-mt 번역 + Moment-DETR",
    "c": "(c) 다국어 CLIP (번역 없음)",
    "d": "(d) 자막 검색 (MiniLM, 서비스 구간 보정)",
    "d_raw": "(d) 자막 검색 (보정 전 자막 구간)",
    "best_dc": "상한: (d)와 (c) 중 나은 쪽",
    "best_da": "상한: (d)와 (a) 중 나은 쪽",
    "random": "무작위 기준선 (기댓값)",
}

INTERPRETATION = """\
1. **말로 설명되는 장면(S)은 자막 검색이 압도적입니다.** IoU ≥ 0.3 기준 10/10, IoU ≥ 0.5 기준 5/10으로, 영상 검색 세 방식(3/10, 1/10)과 무작위 기준선보다 훨씬 높습니다. S에서는 서비스의 구간 보정(시작 2초 앞당김, 최소 6초)이 보정 전 자막 구간보다 정답과 더 잘 맞습니다(IoU ≥ 0.3: 7/10 → 10/10). V에서는 반대로 보정 전이 조금 낫습니다.
2. **화면에만 보이는 장면(V)은 어느 방식도 잘 찾지 못합니다.** 자막 검색은 IoU ≥ 0.3 기준 2/10이고, 그것도 화면 내용이 말과 일부 겹친 질의(#10, #15)입니다. 영상 검색도 1~3/10이며 IoU ≥ 0.5는 1개 이하입니다.
3. **번역 품질은 opus-mt가 확실히 낫지만(의미가 틀린 번역 10개 → 3개), Moment-DETR 검색 정확도는 좋아지지 않았습니다.** 병목은 번역보다 Moment-DETR(영어 QVHighlights 데이터 학습, 1위 구간이 평균 13~20초로 김)입니다. 다국어 CLIP(c)은 V에서 대략 맞는 구간(IoU ≥ 0.3)을 가장 많이 찾았지만 정확한 구간은 0개입니다.
4. **융합으로 얻을 수 있는 최대치가 작습니다.** 질의마다 자막과 영상 중 나은 쪽을 고르는 상한조차 S에서는 적중 수가 자막만 쓸 때와 같습니다. V에서만 늘어나는데, (d)+(c) 상한은 IoU ≥ 0.3 기준 2/10 → 4/10(IoU ≥ 0.5는 0개 그대로), (d)+(a) 상한은 3/10, IoU ≥ 0.5 1/10입니다. 반면 점수 융합이 S 질의의 자막 1위를 영상 결과로 바꾸면 정확도가 떨어질 수 있습니다.

**결론:** 지금 영상 검색 품질로는 점수 융합(α·자막 + (1−α)·영상)의 이득보다 위험이 큽니다. 융합보다 (1) 영상 검색 자체 개선(다국어 CLIP 구간 정교화 또는 한국어 질의에 맞는 모델), (2) 질의 수를 늘린 평가셋 구축이 먼저입니다. 융합을 시험한다면 기본값 off를 유지하고 α를 높게(자막 위주) 두는 것이 안전합니다."""


def seg(s):
    return f"{s[0]:.0f}–{s[1]:.0f}초"


def mark_iou(i):
    return " **✓.5**" if i >= 0.5 else (" ✓.3" if i >= 0.3 else "")


def cell(x):
    return f"{seg(x['seg'])} ({x['iou']:.2f}){mark_iou(x['iou'])}"


def ious_of(rows, m):
    if m == "d_raw":
        return [r["d"]["raw_iou"] if "d" in r else 0.0 for r in rows]
    if m == "best_dc":
        return [max(r.get("d", {}).get("iou", 0.0), r["c"]["iou"]) for r in rows]
    if m == "best_da":
        return [max(r.get("d", {}).get("iou", 0.0), r["a"]["iou"]) for r in rows]
    return [r[m]["iou"] if m in r else 0.0 for r in rows]


def summary_line(label, rows, m):
    n = len(rows)
    if m == "random":
        mi = sum(r["random"]["mean_iou"] for r in rows) / n
        h3 = sum(r["random"]["hit30"] for r in rows) / n
        h5 = sum(r["random"]["hit50"] for r in rows) / n
        return f"| {label} | {METHODS[m]} | {mi:.3f} | {h3:.0%} | {h5:.0%} |"
    ious = ious_of(rows, m)
    c3, c5 = sum(i >= 0.3 for i in ious), sum(i >= 0.5 for i in ious)
    return f"| {label} | {METHODS[m]} | {sum(ious) / n:.3f} | {c3 / n:.0%} ({c3}/{n}) | {c5 / n:.0%} ({c5}/{n}) |"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=os.path.join(tempfile.gettempdir(), "translation_compare", "results.json"))
    parser.add_argument("--output", default=str(ROOT / "docs/experiments/translation_compare.md"))
    args = parser.parse_args()
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    rows, meta = data["rows"], data["meta"]

    qa, qb = TRANSLATION_QUALITY["nllb"], TRANSLATION_QUALITY["opus"]
    count = lambda q, k: sum(v == k for v in q.values())  # noqa: E731
    seg_len = lambda m: sum(r[m]["seg"][1] - r[m]["seg"][0] for r in rows if m in r) / len(rows)  # noqa: E731

    L = ["# 번역 방식별 영상 검색 비교 실험 (+ 자막 검색)", "",
         "자막이 없는 영상의 영상(visual) 검색에서 한국어 질의를 어떻게 처리할지, 그리고 자막 검색과 영상 검색을 점수로 합치는 것이 의미 있는지 판단하기 위한 실험입니다.",
         "현재 서비스는 한국어 자막이 있으면 자막 검색(MiniLM)만, 없으면 한국어 질의를 영어로 번역한 뒤 Moment-DETR로 검색합니다.", "",
         "## 요약", "",
         "| 유형 | 방식 | 평균 IoU | IoU ≥ 0.3 | IoU ≥ 0.5 |", "|---|---|---|---|---|"]
    for t, label in [("S", "S (말로 설명)"), ("V", "V (화면에만 보임)"), (None, "전체")]:
        sub = [r for r in rows if t is None or r["type"] == t]
        for m in ["d", "d_raw", "a", "b", "c", "best_dc", "best_da", "random"]:
            L.append(summary_line(label, sub, m))
    L += ["",
          "- 상한 행은 질의마다 정답을 보고 두 방식 중 나은 쪽을 고른 값으로, 실제로 만들 수 있는 방식이 아니라 융합으로 얻을 수 있는 최대치입니다.",
          f"- 번역 품질 (질의 20개, 작성자 판단): (a) NLLB ✅ {count(qa, 'ok')} · ⚠️ {count(qa, 'part')} · ❌ {count(qa, 'bad')}"
          f" / (b) opus-mt ✅ {count(qb, 'ok')} · ⚠️ {count(qb, 'part')} · ❌ {count(qb, 'bad')}", "",
          "### 해석", "", INTERPRETATION, "",
          "## 실험 설정", "",
          "- 영상: 로컬 한국어 테스트 영상 4개 — "
          + ", ".join(f"{VIDEO_NAMES[k]} {v:.0f}초" for k, v in meta["durations"].items())
          + " (YouTube 다운로드 없음, `ai/experiments/korean_ai_handoff/.../02_Korean_Video_Test`의 영상)",
          "- 영상 feature: CLIP ViT-B/32, 2초 단위 (서비스와 같은 `build_feature`)",
          f"- (a) `{meta['nllb']}` 번역 (`backend/services/translate.py`의 `to_english`) → `predict_moments_hybrid` 1위 구간",
          f"- (b) `{meta['opus']}` 번역 → 같은 `predict_moments_hybrid` 1위 구간",
          f"- (c) `{meta['mclip']}`: 한국어 질의를 그대로 벡터로 만들어 2초 단위 프레임 feature와 코사인 유사도 비교. "
          "구간 선택은 저장소의 `_refine_visual_start`와 같은 규칙(유사도 평활화 → 상위 8개 구간 → 연속 구간 중 (길이, 평균 유사도)가 가장 큰 것)을 영상 전체에 적용. "
          "Moment-DETR는 단어 단위 영어 CLIP 입력이 필요해 다국어 문장 벡터를 넣을 수 없으므로 사용하지 않음",
          f"- (d) 서비스와 같은 Whisper(`{meta['whisper']}`) 자막 + {meta['minilm']}의 1위 자막 구간. "
          f"서비스처럼 시작을 {meta['subtitle_pad_before']:.0f}초 앞당기고 최소 {meta['subtitle_min_len']:.0f}초로 늘린 구간으로 판정하고, 보정 전 구간 결과도 함께 표시. "
          "자막 문장 수: " + ", ".join(f"{VIDEO_NAMES[k]} {n}개({meta['subtitle_language'][k]})" for k, n in meta["subtitle_segments"].items()),
          "- 판정: 1위 구간과 정답 구간의 IoU ≥ 0.3, IoU ≥ 0.5. 정답이 여러 구간이면(#10, #11) 가장 높은 IoU 사용",
          f"- 무작위 기준선: 영상마다 정답 구간 평균 길이("
          + ", ".join(f"{VIDEO_NAMES[k]} {v:.1f}초" for k, v in meta["gt_mean_len"].items())
          + f")의 구간을 무작위 위치에 {meta['random_samples']}번 뽑아 평균 IoU와 적중률 계산 (seed {meta['random_seed']})",
          f"- 1위 구간 평균 길이: (a) {seg_len('a'):.1f}초, (b) {seg_len('b'):.1f}초, (c) {seg_len('c'):.1f}초, (d) {seg_len('d'):.1f}초",
          f"- 환경: {meta['gpu']}", "",
          "## 질의별 결과", "",
          "구간 옆 괄호는 IoU입니다. **✓.5** = IoU ≥ 0.5, ✓.3 = IoU ≥ 0.3. "
          "번역 품질 표시(✅ 의미 보존 · ⚠️ 일부 누락/부정확 · ❌ 의미가 틀림)는 작성자 판단입니다.", "",
          "| # | 영상 | 유형 | 질의 | 정답 | (a) NLLB 번역 | (b) opus-mt 번역 | (a) 1위 | (b) 1위 | (c) 1위 | (d) 자막 1위 [보정 전 IoU] | 무작위 평균 IoU |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        gt = ", ".join(f"{a}–{b}초" for a, b in r["gt"])
        d = r.get("d")
        d_cell = f"{cell(d)} [{d['raw_iou']:.2f}]<br>“{d['text'][:28]}”" if d else "자막 없음"
        L.append(f"| {r['num']} | {VIDEO_NAMES[r['video']]} | {r['type']} | {r['query']} | {gt} | "
                 f"{MARK[qa[r['num']]]} {r['en_a']} | {MARK[qb[r['num']]]} {r['en_b']} | "
                 f"{cell(r['a'])} | {cell(r['b'])} | {cell(r['c'])} | {d_cell} | {r['random']['mean_iou']:.2f} |")
    L += ["", "## 재현 방법", "",
          "프로젝트 루트에서, 백엔드 가상환경과 `backend/.env`(`SCENEFINDER_MINILM_MODEL_PATH` 포함)를 준비한 상태로 실행합니다.", "",
          "    python ai/experiments/translation_compare/run.py --out /tmp/translation_compare",
          "    python ai/experiments/translation_compare/make_report.py --results /tmp/translation_compare/results.json", "",
          "- 질의·정답 구간·번역 품질 판단은 `ai/experiments/translation_compare/queries.py`에 있습니다.",
          "- `run.py`는 영상 feature(`.pt`), Whisper 자막, `results.json`을 `--out` 폴더(기본: 시스템 임시 폴더)에 저장합니다. **저장소 안 폴더를 `--out`으로 지정하지 마세요.** feature 파일은 저장소에 넣지 않습니다.",
          "- 테스트 영상은 `data/raw/korean_test/`에 있으면 그것을, 없으면 `ai/experiments/korean_ai_handoff/remaining_176_files/02_Korean_Video_Test/`(Git LFS)의 영상을 사용합니다.",
          f"- `{meta['opus']}` 모델은 처음 실행할 때 HuggingFace에서 내려받습니다(약 300MB). 다국어 CLIP은 `ai/experiments/korean_ai_handoff/model_assets/multilingual_clip/`의 로컬 모델을 씁니다.",
          "- GPU 기준 전체 실행에 수 분 걸립니다. 같은 입력이면 같은 결과가 나옵니다(무작위 기준선 seed 고정).", "",
          "## 한계", "",
          "- 질의 20개, 영상 4개로 규모가 작습니다. 영상 검색 방식 간 차이는 1~2건이라 통계적으로 의미 있는 차이로 보기 어렵습니다.",
          "- 정답 구간은 프레임을 2~8초 간격으로 보고 한 사람이 정한 대략값입니다.",
          "- (c)의 구간 선택 규칙은 기존 보정 로직을 그대로 쓴 것으로, 이 실험을 위해 조정하지 않았습니다. 상위 8개 구간 기준이라 1위 구간이 최대 16초입니다.",
          "- 상한 행은 정답을 보고 고른 값이라 실제 융합 성능은 이보다 낮습니다.", ""]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print("작성:", out)


if __name__ == "__main__":
    main()
