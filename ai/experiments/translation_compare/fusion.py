"""(d) 자막 검색 + (e) VLM 설명문 검색(Qwen3-VL-4B, 화면 글자 포함)의 실제 융합 실험.

    python ai/experiments/translation_compare/fusion.py --out /tmp/translation_compare [--queries 라벨링.json]

run.py와 captions.py가 --out에 만든 results.json, bench_<영상>_subtitles.json, captions_*.json을 읽고
결과를 --out/fusion_results.json으로 저장합니다. 서비스 코드는 바꾸지 않습니다.
질의·정답 구간은 --queries의 JSON에서 읽습니다. 생략하면 run.py가 쓴 질의 세트(results.json의 queries_source),
그 기록도 없으면 queries.py를 씁니다. 자막이 없는 영상(말소리 없음)은 (d) 없이 설명문만으로 검색합니다.

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
import query_set  # noqa: E402

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
        if not items:
            return []
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


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "translation_compare"))
    parser.add_argument("--queries", default=None,
                        help="라벨링 도구가 저장한 질의 JSON (생략하면 run.py가 쓴 질의 세트)")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    os.chdir(ROOT)
    from dotenv import load_dotenv
    load_dotenv(ROOT / "backend" / ".env")
    from ai.features.fusion_search import get_semantic_model

    res = load_json(out / "results.json")
    source = res["meta"].get("queries_source")
    queries_path = args.queries or (source if source and source.endswith(".json") else None)
    if queries_path and not Path(queries_path).is_absolute() and not Path(queries_path).exists():
        queries_path = ROOT / queries_path   # results.json에는 저장소 루트 기준 경로로 기록됨
    qs = query_set.load(queries_path)
    print("질의:", qs.source, f"({len(qs.queries)}개)")

    durs = res["meta"]["durations"]
    missing = []
    for key in qs.video_keys:
        if key not in durs:
            missing.append(f"results.json에 {key} 영상이 없음 → run.py를 같은 --queries로 다시 실행")
        if not (out / f"bench_{key}_subtitles.json").exists():
            missing.append(f"bench_{key}_subtitles.json 없음 → run.py를 같은 --queries로 다시 실행")
    caps_all = {}
    for v in (CAPTION_VARIANT, "qwen_excl"):
        path = out / f"captions_{v}.json"
        caps_all[v] = load_json(path)["videos"] if path.exists() else {}
    for key in qs.video_keys:
        if key not in caps_all[CAPTION_VARIANT]:
            missing.append(f"captions_{CAPTION_VARIANT}.json에 {key} 영상이 없음 → captions.py를 같은 --queries로 실행")
    if missing:
        sys.exit("\n".join(missing))
    subs_all = {k: load_json(out / f"bench_{k}_subtitles.json")["segments"] for k in qs.video_keys}
    prev_rows = {r["num"]: r for r in res["rows"]}
    S = Searcher(get_semantic_model(model_type="finetuned"))

    rows, mismatch, checked = [], 0, 0
    for num, key, typ, ko, gts in qs.queries:
        subs = [dict(s, source="sub") for s in subs_all[key]]
        caps = [dict(c, source="cap") for c in caps_all[CAPTION_VARIANT][key]]
        out_row = {"num": num, "video": key, "type": typ, "query": ko, "gt": gts}

        # (d) 재현: 같은 질의면 run.py의 (d) 1위 구간과 같아야 함 (정답 구간을 고쳐도 비교되도록 IoU 대신 구간 비교)
        sub_top = (S.rank(ko, subs) or [None])[0]
        d_seg = widen_subtitle((sub_top["start_time"], sub_top["end_time"])) if sub_top else None
        prev = prev_rows.get(num)
        if prev and prev["query"] == ko and prev["video"] == key:
            checked += 1
            prev_seg = tuple(prev["d"]["seg"]) if "d" in prev else None
            if (d_seg is None) != (prev_seg is None) or (d_seg and any(abs(x - y) > 1e-6 for x, y in zip(d_seg, prev_seg))):
                mismatch += 1
        out_row["d"] = ({"seg": d_seg, "iou": best_iou(d_seg, gts), "score": sub_top["score"]} if sub_top
                        else {"seg": None, "iou": 0.0, "score": None})   # 자막 없음

        # (e) 단독 + 구간 규칙
        cap_top = S.rank(ko, caps)[0]
        single = S.single_scores(ko, caps)
        for rule in ("M0", "M1", "M2"):
            seg = caption_span(cap_top, caps, rule, single, durs[key])
            out_row[f"e_{rule}"] = {"seg": seg, "iou": best_iou(seg, gts), "score": cap_top["score"]}

        # B: 각각 검색 후 점수가 높은 쪽
        for rule in ("M0", "M1", "M2"):
            if sub_top and sub_top["score"] >= cap_top["score"]:
                pick = {"seg": d_seg, "from": "자막"}
            else:
                pick = {"seg": out_row[f"e_{rule}"]["seg"], "from": "설명문"}
            out_row[f"B_{rule}"] = {**pick, "iou": best_iou(pick["seg"], gts),
                                    "score": max(sub_top["score"] if sub_top else -1.0, cap_top["score"])}

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
        excl = None
        if key in caps_all["qwen_excl"]:
            ex_top = S.rank(ko, [dict(c, source="cap") for c in caps_all["qwen_excl"][key]])[0]
            ex_seg = (float(ex_top["start_time"]), float(ex_top["end_time"]))
            excl = {"seg": ex_seg, "iou": best_iou(ex_seg, gts), "text": ex_top["text"]}
        out_row["text_ablation"] = {
            "incl": {"seg": out_row["e_M0"]["seg"], "iou": out_row["e_M0"]["iou"], "text": cap_top["text"]},
            "stripped": {"seg": st_seg, "iou": best_iou(st_seg, gts), "text": st_top["text"]},
            "excl": excl,
            "quoted": [m.group(0) for c in caps_all[CAPTION_VARIANT][key]
                       if any(min(c["end_time"], b) - max(c["start_time"], a) > 0 for a, b in gts)
                       for m in QUOTE_RE.finditer(c["text"])],
        }
        rows.append(out_row)
        print(f"#{num:2d} {typ} d={out_row['d']['iou']:.2f} e0={out_row['e_M0']['iou']:.2f} "
              f"e1={out_row['e_M1']['iou']:.2f} e2={out_row['e_M2']['iou']:.2f} A={out_row['A']['iou']:.2f}({kind}) "
              f"B0={out_row['B_M0']['iou']:.2f}({out_row['B_M0']['from']}) B2={out_row['B_M2']['iou']:.2f}", flush=True)

    meta = {"queries_source": qs.source, "caption_variant": CAPTION_VARIANT, "merge_delta": MERGE_DELTA,
            "merge_max_bins": MERGE_MAX_BINS, "d_reproduction_checked": checked, "d_reproduction_mismatches": mismatch}
    (out / "fusion_results.json").write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    print(f"(d) 재현 불일치: {mismatch}/{checked} | 저장:", out / "fusion_results.json")


if __name__ == "__main__":
    main()
