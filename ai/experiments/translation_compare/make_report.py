"""run.py 결과(results.json)로 docs/experiments/translation_compare.md를 만듭니다.

    python ai/experiments/translation_compare/make_report.py [--results 결과.json] [--output 문서.md]

'해석' 절은 작성자가 결과를 보고 쓴 내용입니다. 실험 결과가 바뀌면 함께 고쳐야 합니다.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from queries import QUERIES, TRANSLATION_QUALITY, VIDEO_NAMES

try:  # V 질의별 (e) 결과 판단 (작성자). 없으면 표에서 판단 열을 비움
    from queries import VLM_V_ANALYSIS
except ImportError:
    VLM_V_ANALYSIS = {}

ROOT = Path(__file__).resolve().parents[3]
MARK = {"ok": "✅", "part": "⚠️", "bad": "❌"}
E_KEYS = []  # 결과에 있는 (e) 변형 (main에서 채움)
E_HEAD = {"e_qwen_excl": "(e) Qwen·글자 제외 1위", "e_varco_excl": "(e) VARCO·글자 제외 1위", "e_qwen_incl": "(e) Qwen·글자 포함 1위"}
METHODS = {
    "a": "(a) NLLB 번역 + Moment-DETR",
    "b": "(b) opus-mt 번역 + Moment-DETR",
    "c": "(c) 다국어 CLIP (번역 없음)",
    "d": "(d) 자막 검색 (MiniLM, 서비스 구간 보정)",
    "d_raw": "(d) 자막 검색 (보정 전 자막 구간)",
    "e_qwen_excl": "(e) VLM 설명문 검색 — Qwen3-VL-4B, 화면 글자 제외",
    "e_varco_excl": "(e) VLM 설명문 검색 — VARCO-1.7B, 화면 글자 제외",
    "e_qwen_incl": "(e) VLM 설명문 검색 — Qwen3-VL-4B, 화면 글자 포함",
    "best_de": "상한: (d)와 (e) Qwen·글자 제외 중 나은 쪽",
    "best_de_incl": "상한: (d)와 (e) Qwen·글자 포함 중 나은 쪽",
    "best_dc": "상한: (d)와 (c) 중 나은 쪽",
    "best_da": "상한: (d)와 (a) 중 나은 쪽",
    "random": "무작위 기준선 (기댓값)",
}

INTERPRETATION = """\
1. **말로 설명되는 장면(S)은 자막 검색(d)이 압도적입니다.** IoU ≥ 0.3 기준 10/10, IoU ≥ 0.5 기준 5/10입니다. 영상 검색(a)(b)(c)와 VLM 설명문 검색(e)은 모두 2~3/10에 그칩니다. S에서는 서비스의 구간 보정(시작 2초 앞당김, 최소 6초)이 보정 전보다 정답과 더 잘 맞습니다(IoU ≥ 0.3: 7/10 → 10/10).
2. **화면에만 보이는 장면(V)은 (e) Qwen3-VL-4B·화면 글자 포함이 가장 좋습니다.** IoU ≥ 0.3 기준 4/10, IoU ≥ 0.5 기준 3/10으로, 정확한 구간(IoU ≥ 0.5)을 2개 이상 찾은 유일한 방식입니다. 화면 글자를 제외하면 Qwen은 1/10로 다국어 CLIP(c, 3/10)보다도 낮습니다. 다만 아래 '화면 글자 덕분인지' 절의 측정으로 보면, 적중한 4개 모두 인용된 화면 글자를 지워도 적중해 **화면 글자보다 화면 내용 설명 덕분**이었습니다(프롬프트에 따라 설명문 자체가 달라짐). VARCO(글자 제외)는 3/10이지만, 지시와 달리 화면 자막을 읽어 설명문에 넣은 경우가 있어 순수한 '화면만' 결과로 보기 어렵습니다.
3. **(e) 글자 제외 Qwen의 V 오답 원인:** 정답 장면 설명문에 내용이 있는데 1위로 못 찾은 경우(검색 실패) 3개, 설명문이 틀리거나 빠진 경우(두부를 '채소·냉동 블록', 떡볶이를 '떡국'으로 설명 등) 4개, 정답 구간이 설명문 검색 최대 길이(6초)보다 훨씬 길어 IoU 0.3에 도달할 수 없는 경우 2개입니다(일부 중복). 오답 5개는 정답 바로 옆 2초 구간이 1위였습니다(정답 후보 2위). 정답 구간이 2~3초로 짧아 한 칸만 어긋나도 IoU 0이 됩니다.
4. **번역 품질은 opus-mt가 확실히 낫지만(의미가 틀린 번역 10개 → 3개), Moment-DETR 검색 정확도는 좋아지지 않았습니다.** 병목은 번역보다 Moment-DETR(영어 QVHighlights 데이터 학습, 1위 구간이 평균 13~20초로 김)입니다.
5. **융합 상한은 (d)+(e) 글자 포함이 가장 높습니다.** 질의마다 나은 쪽을 고르는 상한이 전체 IoU ≥ 0.3 기준 15/20, IoU ≥ 0.5 기준 8/20으로, 자막만(12/20, 5/20)이나 (d)+(c)(14/20, 5/20)보다 큽니다. 자막 검색과 설명문 검색은 **둘 다 같은 MiniLM 코사인 유사도**라 점수 척도가 같아, Moment-DETR와 섞을 때의 점수 정규화 문제가 없습니다. 실제로 구현 가능한 융합 결과는 아래 '(d)+(e) 실제 융합' 절에 있습니다.

**결론:** 점수 융합을 한다면 영상 쪽은 Moment-DETR 대신 **VLM 설명문 검색**이 더 유망합니다. 실제 융합(아래 절)에서 자막+설명문을 하나의 목록으로 검색하는 방식 A가 IoU ≥ 0.5 기준 5/20 → 10/20으로 가장 좋았습니다. 다만 (1) 질의 20개 규모라 평가셋 확대가 먼저이고, (2) 장면당 처리 시간이 크므로(아래 처리 시간 표) 묶음 처리를 전제로 비용을 따져야 하며, (3) 성능은 화면 설명 품질(사물 오인식)에 좌우됩니다."""


def seg(s):
    # 아주 짧은 마지막 구간(예: 32.0–32.1초)이 '32–32초'로 보이지 않게 소수 1자리로 표시
    if round(s[0]) == round(s[1]):
        return f"{s[0]:.1f}–{s[1]:.1f}초"
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
    if m == "best_de":
        return [max(r.get("d", {}).get("iou", 0.0), r.get("e_qwen_excl", {}).get("iou", 0.0)) for r in rows]
    if m == "best_de_incl":
        return [max(r.get("d", {}).get("iou", 0.0), r.get("e_qwen_incl", {}).get("iou", 0.0)) for r in rows]
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


def vlm_section(rows, meta):
    """(e) VLM 설명문 방식의 처리 시간·메모리, 설명문 예시, V 질의 분석."""
    caps = meta["captions"]
    label = {"qwen_excl": "Qwen3-VL-4B · 글자 제외", "varco_excl": "VARCO-1.7B · 글자 제외", "qwen_incl": "Qwen3-VL-4B · 글자 포함"}
    variants = [k[2:] for k in E_KEYS]
    L = ["", "## (e) VLM 장면 설명문 검색 상세", "",
         "2초마다 가운데 프레임 1장을 VLM에 넣어 한국어 한 문장 설명을 만들고, 그 설명문을 자막처럼 같은 MiniLM으로 검색했습니다(자막용 구간 보정은 적용하지 않음).", ""]
    L += ["### 모델과 라이선스", ""]
    for v in variants:
        m = caps[v]
        L.append(f"- {label[v]}: `{m['model']}` ({m['dtype']}), 라이선스 **{m['license']}**")
    L += ["", "> VARCO-VISION-2.0은 **CC-BY-NC-4.0(비상업적 이용만 허용)** 라이선스입니다. 연구·공모전 실험에는 쓸 수 있지만 상업 서비스에 넣을 수 없습니다.", "",
          f"- 프롬프트(글자 제외): {caps[variants[0]]['prompt']}"]
    if "qwen_incl" in caps:
        L.append(f"- 프롬프트(글자 포함): {caps['qwen_incl']['prompt']}")
    m0 = caps[variants[0]]
    L += [f"- 프레임: {m0['frame_interval_sec']:.0f}초 간격(구간 가운데 시점), 긴 변 {m0['max_side_px']}px, greedy 생성 최대 {m0['max_new_tokens']}토큰", ""]

    L += ["### 처리 시간과 GPU 메모리", "",
          "| 변형 | 장당 시간 (1장씩) | 장당 시간 (묶음 " + str(m0["batch_size"]) + "장) | 두부 165초 영상 (1장씩 / 묶음) | 짧은 영상 평균 (1장씩) | GPU 최대 메모리 (1장씩 / 묶음) |",
          "|---|---|---|---|---|---|"]
    for v in variants:
        m = caps[v]; sg, bt = m["single"], m.get("batch")
        frames = sum(x["frames"] for x in sg.values()); tot = sum(x["total_sec"] for x in sg.values())
        short = [x["total_sec"] for k, x in sg.items() if k != "tofu"]
        if bt:
            bframes = sum(x["frames"] for k, x in bt.items() if k != "peak_gpu_gib")
            btot = sum(x["total_sec"] for k, x in bt.items() if k != "peak_gpu_gib")
            bcell, tofu_b, mem_b = f"{btot / bframes:.2f}초 (×{tot / btot:.1f} 빠름)", f"{bt['tofu']['total_sec']:.0f}초", f"{bt['peak_gpu_gib']:.1f} GiB"
        else:
            bcell, tofu_b, mem_b = "측정 안 함", "-", "-"
        L.append(f"| {label[v]} | {tot / frames:.2f}초 | {bcell} | {sg['tofu']['total_sec']:.0f}초 / {tofu_b} | "
                 f"{sum(short) / len(short):.0f}초 | {m['peak_gpu_gib_single']:.1f} GiB / {mem_b} |")
    L += ["", f"- 측정 환경: {m0['gpu']}, transformers(sdpa), 프레임 추출 시간 제외(전체 {m0['frame_extract_sec']:.0f}초). 설명문은 1장씩 처리한 결과를 사용했습니다.", ""]

    # 설명문 예시: 영상마다 5개 (V 질의 정답 구간 포함)
    L += ["### 설명문 예시 (영상별 5개)", "", "★ = V 질의의 정답 구간에 해당하는 장면", ""]
    v_spans = {}
    for num, key, typ, ko, gts in QUERIES:
        if typ == "V":
            for a, b in gts:
                v_spans.setdefault(key, []).append((num, (a + b) / 2))
    main_v = variants[0]
    for key in VIDEO_NAMES:
        segs = meta["captions"] and None
        caption_rows = json.loads(Path(CAPTION_FILES[main_v]).read_text(encoding="utf-8"))["videos"][key]
        picks = []
        for num, t in v_spans.get(key, []):
            idx = min(range(len(caption_rows)), key=lambda i: abs((caption_rows[i]["start_time"] + caption_rows[i]["end_time"]) / 2 - t))
            if idx not in [p for p, _ in picks]:
                picks.append((idx, f"★#{num}"))
        n = len(caption_rows); i = 0
        while len(picks) < 5 and i < 5:
            idx = round((i + 0.5) * n / 5) % n
            if idx not in [p for p, _ in picks]:
                picks.append((idx, ""))
            i += 1
        k2 = 0
        while len(picks) < 5 and k2 < n:
            if k2 not in [p for p, _ in picks]:
                picks.append((k2, ""))
            k2 += 1
        picks.sort()
        L += [f"**{VIDEO_NAMES[key]}**", "", "| 구간 | " + " | ".join(label[v] for v in variants) + " |", "|---|" + "---|" * len(variants)]
        all_caps = {v: json.loads(Path(CAPTION_FILES[v]).read_text(encoding="utf-8"))["videos"][key] for v in variants}
        for idx, tag in picks:
            c = all_caps[main_v][idx]
            L.append(f"| {c['start_time']:.0f}–{c['end_time']:.0f}초 {tag} | " + " | ".join(all_caps[v][idx]["text"].replace("|", "/") for v in variants) + " |")
        L.append("")

    # V 질의 분석
    L += ["### V 질의별 결과와 틀린 이유", "",
          "적중 기준은 IoU ≥ 0.3입니다. '정답 후보 순위'는 정답과 IoU ≥ 0.3으로 겹치는 검색 후보 중 가장 높은 것이 전체 후보 중 몇 위였는지입니다. "
          "판단은 정답 구간의 설명문을 읽고 작성자가 분류했습니다: **적중** / **검색 실패**(설명문에 해당 내용이 있었는데 1위로 못 찾음) / **설명 없음**(설명문에 해당 내용이 없음).", "",
          "| # | 질의 | " + " | ".join(f"{label[v]} 1위 (IoU) / 정답 후보 순위" for v in variants) + " | 정답 구간 설명문 (" + label[main_v] + ") | "
          + " | ".join(f"판단 ({label[v]})" for v in JUDGED) + " |",
          "|---|---|" + "---|" * (len(variants) + 1 + len(JUDGED))]
    for r in rows:
        if r["type"] != "V":
            continue
        cells = []
        for v in variants:
            e = r[f"e_{v}"]
            rank = f"{e['gt_rank']}/{e['gt_rank_of']}" if e["gt_rank"] else "없음"
            cells.append(f"{seg(e['seg'])} ({e['iou']:.2f}){mark_iou(e['iou'])} / {rank}")
        gt_caps = " / ".join(dict.fromkeys(r[f"e_{main_v}"]["gt_captions"]))[:160].replace("|", "/")
        judged = [VLM_V_ANALYSIS.get(r["num"], {}).get(v, "") for v in JUDGED]
        L.append(f"| {r['num']} | {r['query']} | " + " | ".join(cells) + f" | {gt_caps} | " + " | ".join(judged) + " |")
    L.append("")
    return L


CAPTION_FILES = {}
FUSION_FILE = None

FUSION_METHODS = {
    "d": "(d) 자막 검색 단독",
    "e_M0": "(e) 설명문 단독 — 구간 그대로",
    "e_M1": "(e) 설명문 단독 — 앞뒤 1칸(2초) 확장",
    "e_M2": "(e) 설명문 단독 — 점수가 비슷한 이웃 칸 병합",
    "A": "A: 자막+설명문 하나의 목록으로 검색",
    "B_M0": "B: 각각 검색 후 점수 max (설명문 구간 그대로)",
    "B_M1": "B: 각각 검색 후 점수 max (설명문 앞뒤 1칸 확장)",
    "B_M2": "B: 각각 검색 후 점수 max (설명문 이웃 칸 병합)",
}

FUSION_INTERPRETATION = """\
1. **S(말로 설명되는 장면)는 두 방식 모두 1개 줄었습니다(IoU ≥ 0.3 기준 10/10 → 9/10).** 같은 질의(#1 '두부를 반으로 자르는 장면')에서, 화면을 그대로 묘사한 설명문('두부를 칼로 자르는 장면', 점수 0.497)이 맞는 자막(0.395)을 이겼습니다. 설명문 1위는 정답(13–19초) 바로 다음 칸(20–22초)이었습니다. IoU ≥ 0.5 기준으로는 A가 5/10 → 6/10으로 오히려 늘었고 B는 5/10 그대로입니다.
2. **V(화면에만 보이는 장면)는 A가 가장 좋습니다.** IoU ≥ 0.5 기준 0/10(자막 단독) → 4/10입니다. B는 설명문 단독과 같은 4/10, 3/10인데, #10에서 설명문이 자막을 0.008 차이로 이겨 자막 단독이 맞히던 질의를 놓쳤습니다.
3. **전체로는 A가 IoU ≥ 0.3 기준 12/20 → 13/20, IoU ≥ 0.5 기준 5/20 → 10/20입니다.** A의 이득 일부는 구간 경계 효과입니다. 하나의 목록에서는 연속 자막 사이에 설명문이 끼어 자막 묶음이 짧아지고(#9), 자막과 설명문이 섞인 창은 자막용 구간 보정 없이 더 촘촘한 구간이 됩니다(#4 IoU 0.56 → 0.74).
4. **인접 칸 병합은 IoU ≥ 0.3을 늘리지만 IoU ≥ 0.5를 줄입니다.** 앞뒤 1칸 확장(M1)은 한 칸 차이로 놓친 질의를 IoU ≥ 0.3으로 끌어올리지만(설명문 단독 전체 6/20 → 10/20) 짧은 정답에서는 구간이 길어져 IoU ≥ 0.5가 줄었습니다(V 3/10 → 1/10). 점수가 비슷한 이웃만 병합(M2, 기준 0.03)은 한 번도 병합이 일어나지 않아 M0과 같았습니다.

**결론:** 실제 구현 방식으로는 **A(하나의 목록으로 검색)**가 가장 낫고, S 손실(10 → 9, IoU ≥ 0.3)이 1개 있어 0개는 아닙니다. 서비스에 넣는다면 자막 검색 결과를 먼저 보여주고 설명문 결과를 보조로 붙이거나, 설명문 점수에 작은 감점을 주는 방식을 평가셋을 늘려 비교해야 합니다(이번 20개 질의로 감점값을 정하면 과적합이 됩니다)."""


def fusion_section():
    data = json.loads(Path(FUSION_FILE).read_text(encoding="utf-8"))
    rows, fm = data["rows"], data["meta"]
    L = ["", "## (d)+(e) 실제 융합", "",
         "상한값이 아니라 실제로 구현할 수 있는 방식으로 자막 검색(d)과 VLM 설명문 검색(e, Qwen3-VL-4B·화면 글자 포함)을 합쳤습니다. "
         "모두 같은 Fine-tuned MiniLM 점수를 씁니다. 같은 창 구성 코드로 (d)를 다시 계산해 기존 결과와 일치하는 것을 확인했습니다"
         f"(불일치 {fm['d_reproduction_mismatches']}개).", "",
         "- A: 자막 문장과 설명문을 시간순 하나의 목록으로 합쳐, 연속 1~3개 묶음 창으로 검색. 창이 자막만이면 서비스 구간 보정 적용, 설명문만·섞인 창은 그대로",
         "- B: 자막과 설명문을 각각 검색해 1위 점수가 높은 쪽 사용. 자막이 이기면 서비스 구간 보정, 설명문이 이기면 설명문 구간 규칙 적용",
         f"- 설명문 구간 규칙: 그대로 / 앞뒤 1칸(2초) 확장 / 1위 점수와 {fm['merge_delta']} 이내인 이웃 칸 병합(최대 {fm['merge_max_bins']}칸, 기준값은 실험 전에 정함)", "",
         "| 유형 | 방식 | 평균 IoU | IoU ≥ 0.3 | IoU ≥ 0.5 |", "|---|---|---|---|---|"]
    for t, label in [("S", "S (말로 설명)"), ("V", "V (화면에만 보임)"), (None, "전체")]:
        sub = [r for r in rows if t is None or r["type"] == t]
        n = len(sub)
        for m, name in FUSION_METHODS.items():
            ious = [r[m]["iou"] for r in sub]
            c3, c5 = sum(i >= 0.3 for i in ious), sum(i >= 0.5 for i in ious)
            L.append(f"| {label} | {name} | {sum(ious) / n:.3f} | {c3 / n:.0%} ({c3}/{n}) | {c5 / n:.0%} ({c5}/{n}) |")
    L += ["", "### 해석", "", FUSION_INTERPRETATION, "",
          "### 질의별 결과", "",
          "괄호 안은 IoU, A·B 옆은 1위가 나온 곳입니다.", "",
          "| # | 유형 | 질의 | (d) 자막 | (e) 그대로 | (e) 1칸 확장 | A | B (그대로) | B (1칸 확장) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = lambda x: f"{seg(x['seg'])} ({x['iou']:.2f}){mark_iou(x['iou'])}"  # noqa: E731
        L.append(f"| {r['num']} | {r['type']} | {r['query']} | {c(r['d'])} | {c(r['e_M0'])} | {c(r['e_M1'])} | "
                 f"{c(r['A'])} · {r['A']['from']} | {c(r['B_M0'])} · {r['B_M0']['from']} | {c(r['B_M1'])} · {r['B_M1']['from']} |")

    L += ["", "## 화면 글자 덕분인지, 화면 내용 덕분인지", "",
          "'화면 글자 포함' 설명문으로 맞힌 V 질의가 화면 글자 덕분인지 확인하려고, 설명문에서 따옴표로 인용한 화면 글자만 지우고 같은 방법으로 다시 검색했습니다. "
          "지워도 맞히면 화면 내용 설명 덕분, 지우면 못 맞히면 화면 글자 덕분으로 봅니다. '글자 제외' 프롬프트로 만든 설명문 결과도 함께 적었습니다.", "",
          "| # | 질의 | 글자 포함 (IoU) | 인용 글자 지움 (IoU) | 글자 제외 프롬프트 (IoU) | 정답 구간에 인용된 화면 글자 | 판단 |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["type"] != "V":
            continue
        a = r["text_ablation"]
        inc, stp, exc = a["incl"]["iou"], a["stripped"]["iou"], a["excl"]["iou"]
        if max(inc, stp) < 0.3:
            continue
        if inc >= 0.3 and stp >= 0.3:
            verdict = "화면 내용 (글자를 지워도 적중)" + ("" if exc >= 0.3 else ". 글자 제외 프롬프트로는 놓침 → 프롬프트에 따라 화면 설명 자체가 달라짐")
        elif inc >= 0.3:
            verdict = "화면 글자 (지우면 놓침)"
        else:
            verdict = "인용 글자가 오히려 방해 (지우면 적중)"
        quoted = ", ".join(q for q in a["quoted"] if len(q) > 2)[:80].replace("|", "/") or "-"
        L.append(f"| {r['num']} | {r['query']} | {inc:.2f} | {stp:.2f} | {exc:.2f} | {quoted} | {verdict} |")
    L += ["", "- 글자 포함으로 맞힌 V 질의 4개(#15, #16, #19, #20)는 모두 화면 글자를 지워도 맞혔습니다. 적중의 근거는 화면 글자가 아니라 화면 내용 설명이었습니다.",
          "- 같은 장면이라도 프롬프트(글자 포함/제외)에 따라 생성되는 화면 설명이 달라졌습니다(예: #19 '소스를 뿌리려는 순간' vs '패키지를 든'). 이번 차이가 프롬프트의 일반적인 효과인지는 질의 20개로는 판단할 수 없습니다.",
          "- 따옴표 없이 옮겨 쓴 화면 글자는 지워지지 않았을 수 있습니다.", ""]
    return L



JUDGED = ["qwen_excl", "qwen_incl"]  # 판단을 적은 변형


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=os.path.join(tempfile.gettempdir(), "translation_compare", "results.json"))
    parser.add_argument("--output", default=str(ROOT / "docs/experiments/translation_compare.md"))
    args = parser.parse_args()
    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    for f in Path(args.results).parent.glob("captions_*.json"):
        CAPTION_FILES[f.stem.replace("captions_", "")] = f
    global FUSION_FILE
    fusion = Path(args.results).parent / "fusion_results.json"
    FUSION_FILE = fusion if fusion.exists() else None
    rows, meta = data["rows"], data["meta"]
    global E_KEYS
    E_KEYS = [k for k in ["e_qwen_excl", "e_varco_excl", "e_qwen_incl"] if k in rows[0]]

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
        for m in ["d", "d_raw"] + E_KEYS + ["a", "b", "c"] + (["best_de", "best_de_incl"] if E_KEYS else []) + ["best_dc", "best_da", "random"]:
            if m.startswith("best_de") and (("e_qwen_excl" if m == "best_de" else "e_qwen_incl") not in E_KEYS):
                continue
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
          "| # | 영상 | 유형 | 질의 | 정답 | (a) NLLB 번역 | (b) opus-mt 번역 | (a) 1위 | (b) 1위 | (c) 1위 | (d) 자막 1위 [보정 전 IoU] | "
          + "".join(f"{E_HEAD[k]} | " for k in E_KEYS) + "무작위 평균 IoU |",
          "|" + "---|" * (12 + len(E_KEYS))]
    for r in rows:
        gt = ", ".join(f"{a}–{b}초" for a, b in r["gt"])
        d = r.get("d")
        d_cell = f"{cell(d)} [{d['raw_iou']:.2f}]<br>“{d['text'][:28]}”" if d else "자막 없음"
        L.append(f"| {r['num']} | {VIDEO_NAMES[r['video']]} | {r['type']} | {r['query']} | {gt} | "
                 f"{MARK[qa[r['num']]]} {r['en_a']} | {MARK[qb[r['num']]]} {r['en_b']} | "
                 f"{cell(r['a'])} | {cell(r['b'])} | {cell(r['c'])} | {d_cell} | "
                 + "".join(f"{cell(r[k])} | " for k in E_KEYS) + f"{r['random']['mean_iou']:.2f} |")
    if E_KEYS:
        L += vlm_section(rows, meta)
    if FUSION_FILE:
        L += fusion_section()
    L += ["", "## 재현 방법", "",
          "프로젝트 루트에서, 백엔드 가상환경과 `backend/.env`(`SCENEFINDER_MINILM_MODEL_PATH` 포함)를 준비한 상태로 실행합니다.", "",
          "    python ai/experiments/translation_compare/captions.py --out /tmp/translation_compare   # (e)용 설명문, 선택",
          "    python ai/experiments/translation_compare/run.py --out /tmp/translation_compare",
          "    python ai/experiments/translation_compare/fusion.py --out /tmp/translation_compare     # (d)+(e) 실제 융합, 선택",
          "    python ai/experiments/translation_compare/make_report.py --results /tmp/translation_compare/results.json", "",
          "- 질의·정답 구간·번역 품질 판단은 `ai/experiments/translation_compare/queries.py`에 있습니다.",
          "- `run.py`는 영상 feature(`.pt`), Whisper 자막, `results.json`을 `--out` 폴더(기본: 시스템 임시 폴더)에 저장합니다. **저장소 안 폴더를 `--out`으로 지정하지 마세요.** feature 파일은 저장소에 넣지 않습니다.",
          "- 테스트 영상은 `data/raw/korean_test/`에 있으면 그것을, 없으면 `ai/experiments/korean_ai_handoff/remaining_176_files/02_Korean_Video_Test/`(Git LFS)의 영상을 사용합니다.",
          f"- `{meta['opus']}` 모델은 처음 실행할 때 HuggingFace에서 내려받습니다(약 300MB). 다국어 CLIP은 `ai/experiments/korean_ai_handoff/model_assets/multilingual_clip/`의 로컬 모델을 씁니다.",
          "- (e)용 `captions.py`는 처음 실행할 때 `Qwen/Qwen3-VL-4B-Instruct`(약 8.9GB)와 `NCSOFT/VARCO-VISION-2.0-1.7B`(약 4.2GB)를 내려받고, 설명문을 `--out`의 `captions_<변형>.json`으로 저장합니다. `run.py`는 이 파일이 있으면 (e)를 함께 평가합니다. GPU 메모리는 최대 약 9GiB 사용합니다.",
          "- 모델 다운로드가 멈추면(Hugging Face Xet 전송 문제) `HF_HUB_DISABLE_XET=1`을 붙여 다시 실행하세요.",
          "- GPU 기준 (a)~(d) 실행은 수 분, (e) 설명문 생성은 변형 3개에 약 20분 걸립니다. 같은 입력이면 같은 결과가 나옵니다(무작위 기준선 seed 고정, greedy 생성).", "",
          "## 한계", "",
          "- 질의 20개, 영상 4개로 규모가 작습니다. 영상 검색 방식 간 차이는 1~2건이라 통계적으로 의미 있는 차이로 보기 어렵습니다.",
          "- 정답 구간은 프레임을 2~8초 간격으로 보고 한 사람이 정한 대략값입니다.",
          "- (c)의 구간 선택 규칙은 기존 보정 로직을 그대로 쓴 것으로, 이 실험을 위해 조정하지 않았습니다. 상위 8개 구간 기준이라 1위 구간이 최대 16초입니다.",
          "- 상한 행은 정답을 보고 고른 값이라 실제 융합 성능은 이보다 낮습니다.",
          "- (e) 설명문 검색은 2초 단위 설명문을 최대 3개까지 묶어 검색하므로 1위 구간이 최대 6초입니다. 정답이 20초 이상인 질의(#6 29초, #7 21초)는 IoU 0.3에 도달할 수 없습니다.",
          "- 정답 구간이 2~3초로 짧은 질의는 2초 구간 하나만 어긋나도 IoU가 0이 됩니다. (e)의 오답 중 여러 개가 정답 바로 옆 구간이었습니다.",
          "- VARCO(글자 제외)는 지시와 달리 화면 자막을 그대로 옮겨 쓴 설명문이 있습니다(예: 다이소 4–6초). '글자 제외' 결과에 말 내용이 일부 섞여 있습니다.",
          "- VLM 설명문은 greedy 생성이라 같은 입력이면 같은 결과지만, transformers나 모델 버전이 바뀌면 달라질 수 있습니다.", ""]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print("작성:", out)


if __name__ == "__main__":
    main()
