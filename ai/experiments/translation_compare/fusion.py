"""(d) 자막 검색 + (e) VLM 설명문 검색(Qwen3-VL-4B, 화면 글자 포함)의 실제 융합 실험.

    python ai/experiments/translation_compare/fusion.py --out /tmp/translation_compare

run.py와 captions.py가 --out에 만든 results.json, bench_<영상>_subtitles.json, captions_*.json을 읽고
결과를 --out/fusion_results.json으로 저장합니다. 서비스 코드는 바꾸지 않습니다.

방식
  (e) 단독: 설명문만 검색. 구간 규칙 M0(그대로) / M1(앞뒤 1칸 확장) / M2(점수가 비슷한 이웃 칸 병합)
  A: 자막 문장과 설명문을 시간순 하나의 목록으로 합쳐 검색 (1~3개 묶음 창은 서로 섞일 수 있음)
  B: 자막·설명문을 각각 검색해 점수가 높은 쪽 1위 사용 (자막은 서비스 구간 보정, 설명문은 M0/M1/M2)
화면 글자 분석: '글자 포함' 설명문에서 따옴표로 인용된 화면 글자를 지우고 다시 검색
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import ROOT, SUBTITLE_MIN_LEN, SUBTITLE_PAD_BEFORE, best_iou  # noqa: E402  (ROOT를 sys.path에 추가)

from sentence_transformers import util  # noqa: E402

CAPTION_VARIANT = "qwen_incl"
MERGE_DELTA = 0.03       # M2: 1위 점수와 이 이내인 이웃 칸만 병합 (실험 전에 정한 값, 질의에 맞춰 조정하지 않음)
MERGE_MAX_BINS = 5       # M2: 최대 10초
CLIP_LEN = 2.0
QUOTE_RE = re.compile(r"['\"“‘「『][^'\"”’」』]*['\"”’」』]|['\"“‘「『][^'\"”’」』]*$")


def strip_screen_text(text):
    """설명문에서 따옴표로 인용한 화면 글자를 지웁니다. (따옴표 없이 옮긴 글자는 남을 수 있음)"""
    return re.sub(r"\s+", " ", QUOTE_RE.sub("", text)).strip()


class Searcher:
    """fusion_search.get_semantic_subtitle_candidates와 같은 방식(연속 1~3개 문장 묶음 창)으로 모든 창의 점수를 계산."""

    def __init__(self, model):
        self.model = model

    def rank(self, query, items):
        windows = []
        for size in (1, 2, 3):
            for i in range(len(items) - size + 1):
                group = items[i:i + size]
                windows.append({"start_time": group[0]["start_time"], "end_time": group[-1]["end_time"],
                                "text": " ".join(s["text"] for s in group), "first": i, "last": i + size - 1,
                                "sources": {s.get("source", "sub") for s in group}})
        emb = self.model.encode([w["text"] for w in windows], convert_to_tensor=True)
        q = self.model.encode(query, convert_to_tensor=True)
        scores = util.cos_sim(q, emb)[0].tolist()
        for w, s in zip(windows, scores):
            w["score"] = round(float(s), 4)
        return sorted(windows, key=lambda w: -w["score"])

    def single_scores(self, query, items):
        emb = self.model.encode([s["text"] for s in items], convert_to_tensor=True)
        q = self.model.encode(query, convert_to_tensor=True)
        return [float(x) for x in util.cos_sim(q, emb)[0].tolist()]


def widen_subtitle(seg):
    start = max(0.0, seg[0] - SUBTITLE_PAD_BEFORE)
    return (start, max(seg[1], start + SUBTITLE_MIN_LEN))


def caption_span(top, caps, rule, single=None, dur=None):
    """설명문 1위 창의 구간. M0 그대로 / M1 앞뒤 1칸 / M2 점수가 비슷한 이웃 칸 병합."""
    first, last = top["first"], top["last"]
    if rule == "M1":
        first, last = max(0, first - 1), min(len(caps) - 1, last + 1)
    elif rule == "M2":
        floor = top["score"] - MERGE_DELTA
        while last - first + 1 < MERGE_MAX_BINS:
            left = single[first - 1] if first > 0 else -1
            right = single[last + 1] if last + 1 < len(caps) else -1
            if max(left, right) < floor:
                break
            if left >= right:
                first -= 1
            else:
                last += 1
    end = caps[last]["end_time"] if dur is None else min(caps[last]["end_time"], dur)
    return (float(caps[first]["start_time"]), float(end))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "translation_compare"))
    args = parser.parse_args()
    out = Path(args.out).resolve()
    os.chdir(ROOT)
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    from ai.features.fusion_search import get_semantic_model

    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    caps_all = {v: json.loads((out / f"captions_{v}.json").read_text(encoding="utf-8"))["videos"]
                for v in (CAPTION_VARIANT, "qwen_excl")}
    subs_all = {k: json.loads((out / f"bench_{k}_subtitles.json").read_text(encoding="utf-8"))["segments"]
                for k in res["meta"]["durations"]}
    durs = res["meta"]["durations"]
    S = Searcher(get_semantic_model(model_type="finetuned"))

    rows, mismatch = [], 0
    for r in res["rows"]:
        key, ko, gts = r["video"], r["query"], [tuple(g) for g in r["gt"]]
        subs = [dict(s, source="sub") for s in subs_all[key]]
        caps = [dict(c, source="cap") for c in caps_all[CAPTION_VARIANT][key]]
        out_row = {"num": r["num"], "type": r["type"], "query": ko, "gt": gts}

        # (d) 재현: run.py의 (d)와 같아야 함
        sub_rank = S.rank(ko, subs)
        sub_top = sub_rank[0]
        d_seg = widen_subtitle((sub_top["start_time"], sub_top["end_time"]))
        if abs(best_iou(d_seg, gts) - r["d"]["iou"]) > 1e-6:
            mismatch += 1
        out_row["d"] = {"seg": d_seg, "iou": best_iou(d_seg, gts), "score": sub_top["score"]}

        # (e) 단독 + 구간 규칙
        cap_rank = S.rank(ko, caps)
        cap_top = cap_rank[0]
        single = S.single_scores(ko, caps)
        for rule in ("M0", "M1", "M2"):
            seg = caption_span(cap_top, caps, rule, single, durs[key])
            out_row[f"e_{rule}"] = {"seg": seg, "iou": best_iou(seg, gts), "score": cap_top["score"]}

        # B: 각각 검색 후 점수가 높은 쪽
        for rule in ("M0", "M1", "M2"):
            if sub_top["score"] >= cap_top["score"]:
                pick = {"seg": d_seg, "from": "자막"}
            else:
                pick = {"seg": out_row[f"e_{rule}"]["seg"], "from": "설명문"}
            out_row[f"B_{rule}"] = {**pick, "iou": best_iou(pick["seg"], gts),
                                    "score": max(sub_top["score"], cap_top["score"])}

        # A: 하나의 시간순 목록으로 합쳐 검색 (창이 자막·설명문을 섞을 수 있음)
        merged = sorted(subs + caps, key=lambda x: (x["start_time"], x["source"]))
        top = S.rank(ko, merged)[0]
        raw = (float(top["start_time"]), float(top["end_time"]))
        if top["sources"] == {"sub"}:
            seg, kind = widen_subtitle(raw), "자막만"
        elif top["sources"] == {"cap"}:
            seg, kind = raw, "설명문만"
        else:
            seg, kind = raw, "섞임"
        out_row["A"] = {"seg": seg, "iou": best_iou(seg, gts), "score": top["score"], "from": kind, "text": top["text"]}

        # 화면 글자 분석: 따옴표 안 화면 글자를 지운 설명문으로 다시 검색 (M0)
        stripped = [dict(c, text=strip_screen_text(c["text"])) for c in caps]
        st_top = S.rank(ko, stripped)[0]
        st_seg = (float(st_top["start_time"]), float(st_top["end_time"]))
        excl_caps = [dict(c, source="cap") for c in caps_all["qwen_excl"][key]]
        ex_top = S.rank(ko, excl_caps)[0]
        out_row["text_ablation"] = {
            "incl": {"seg": out_row["e_M0"]["seg"], "iou": out_row["e_M0"]["iou"], "text": cap_top["text"]},
            "stripped": {"seg": st_seg, "iou": best_iou(st_seg, gts), "text": st_top["text"]},
            "excl": {"seg": (float(ex_top["start_time"]), float(ex_top["end_time"])),
                     "iou": best_iou((float(ex_top["start_time"]), float(ex_top["end_time"])), gts), "text": ex_top["text"]},
            "quoted": [m.group(0) for c in caps_all[CAPTION_VARIANT][key]
                       if any(min(c["end_time"], b) - max(c["start_time"], a) > 0 for a, b in gts)
                       for m in QUOTE_RE.finditer(c["text"])],
        }
        rows.append(out_row)
        print(f"#{r['num']:2d} {r['type']} d={out_row['d']['iou']:.2f} e0={out_row['e_M0']['iou']:.2f} "
              f"e1={out_row['e_M1']['iou']:.2f} e2={out_row['e_M2']['iou']:.2f} A={out_row['A']['iou']:.2f}({kind}) "
              f"B0={out_row['B_M0']['iou']:.2f}({out_row['B_M0']['from']}) B2={out_row['B_M2']['iou']:.2f}", flush=True)

    meta = {"caption_variant": CAPTION_VARIANT, "merge_delta": MERGE_DELTA, "merge_max_bins": MERGE_MAX_BINS,
            "d_reproduction_mismatches": mismatch}
    (out / "fusion_results.json").write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    print("(d) 재현 불일치:", mismatch, "| 저장:", out / "fusion_results.json")


if __name__ == "__main__":
    main()
