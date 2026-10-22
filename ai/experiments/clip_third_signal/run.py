"""CLIP 화면 검색을 세 번째 신호로 붙였을 때 비교 (dev). 설계: docs/experiments/clip_third_signal.md

    CUDA_VISIBLE_DEVICES= python ai/experiments/clip_third_signal/run.py \
        --queries ~/scenefinder_eval/labels_draft.json --subset dev \
        --features ~/scenefinder_eval/results_v2_whisper_turbo_b8 --out ~/scenefinder_eval/clip_third_signal
    python ai/experiments/clip_third_signal/run.py --report ~/scenefinder_eval/clip_third_signal/results.json

- (a) 현재 서비스(자막 MiniLM + 설명문 e5, captions.fused_search와 같은 규칙), (b) a + 다국어 CLIP, (c) a + Moment-DETR
- 자막·설명문 파일은 서비스 서버의 파일(data/processed/)을 읽기만 함 (자막 창 임베딩 캐시도 쓰지 않고 직접 계산)
- --check-api URL을 주면 (a) 결과를 실제 서비스 POST /api/search 결과와 비교
"""
import argparse
import csv
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ai/experiments/translation_compare"))
os.environ.setdefault("CAPTION_SEARCH_ENABLED", "1")

TOP_K = 5
MCLIP = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
MCLIP_DIR = ROOT / "ai/experiments/korean_ai_handoff/model_assets/multilingual_clip"
SCOPE_TSV = ROOT / "docs/experiments/clip_third_signal_scope.tsv"


# ===================== 신호별 후보 =====================

def zscore_of(score, all_scores, min_n, min_std):
    n = len(all_scores)
    if n < min_n:
        return None
    mean = sum(all_scores) / n
    std = (sum((s - mean) ** 2 for s in all_scores) / n) ** 0.5
    if std < min_std:
        return None
    return (score - mean) / std


class Signals:
    def __init__(self, feat_dir):
        import torch
        from sentence_transformers import SentenceTransformer

        from ai.features.fusion_search import get_semantic_model
        from backend.services import captions

        self.torch = torch
        self.captions = captions
        self.cfg = captions._cfg()
        self.minilm = get_semantic_model(model_type="finetuned")
        self.mclip = SentenceTransformer(str(MCLIP_DIR) if MCLIP_DIR.is_dir() else MCLIP, device="cpu")
        self.feat_dir = Path(feat_dir).expanduser()
        self._sub_cache = {}

    def feature_path(self, key):
        return self.feat_dir / f"bench_{key}_clip_features.pt"

    def subtitle(self, yid, subtitles, query):
        """[(cand, z)] 점수 내림차순. 서비스와 같은 창·점수(임베딩은 직접 계산, 캐시 파일 안 씀)."""
        from sentence_transformers import util
        if not subtitles:
            return []
        if yid not in self._sub_cache:
            wins = self.captions.windows(subtitles)
            emb = self.minilm.encode([w["text"] for w in wins], convert_to_tensor=True).float().cpu()
            self._sub_cache[yid] = (wins, emb)
        wins, emb = self._sub_cache[yid]
        q = self.minilm.encode(query, convert_to_tensor=True).float().cpu()
        scores = util.cos_sim(q, emb)[0].tolist()
        z = self.captions._zscores(scores)
        out = [{**w, "score": s, "z": (z[i] if z else None), "source": "subtitle"} for i, (w, s) in enumerate(zip(wins, scores))]
        return sorted(out, key=lambda m: -m["score"]), z is not None

    def caption(self, index, query):
        qv = self.captions._encode_e5([query], self.cfg["embed_model"], "query: ")[0].float().cpu()
        scores = (index["emb"].float() @ qv).tolist()
        z = self.captions._zscores(scores)
        out = [{**w, "score": s, "z": (z[i] if z else None), "source": "caption"} for i, (w, s) in enumerate(zip(index["windows"], scores))]
        return sorted(out, key=lambda m: -m["score"]), z is not None

    def clip(self, key, duration, query):
        """eval_v2 (c)와 같은 구간 규칙. 후보 점수 = 구간 칸들의 평활화 유사도 평균, z는 전체 칸 기준."""
        import torch.nn.functional as F
        from ai.features.run_moment_detr_inference import CLIP_LEN, VISUAL_TOP_K, _make_contiguous_clusters, _smooth_scores
        torch = self.torch
        vf = F.normalize(torch.load(self.feature_path(key), map_location="cpu").float(), dim=-1)
        q = F.normalize(torch.tensor(self.mclip.encode([query]))[0].float(), dim=-1)
        sm = _smooth_scores(vf @ q)
        bins = sm.tolist()
        top = torch.topk(sm, k=min(VISUAL_TOP_K, len(sm))).indices.tolist()
        multi = [c for c in _make_contiguous_clusters(top) if len(c) >= 2]
        ranked = sorted(multi, key=lambda c: (len(c), float(sm[c].mean())), reverse=True)
        ranked += [[i] for i in torch.argsort(sm, descending=True).tolist()]
        out = []
        for c in ranked:
            score = float(sm[c].mean())
            out.append({"start_time": float(min(c) * CLIP_LEN), "end_time": float(min((max(c) + 1) * CLIP_LEN, duration)),
                        "score": score, "z": zscore_of(score, bins, self.captions.ZSCORE_MIN_WINDOWS, self.captions.ZSCORE_MIN_STD),
                        "source": "clip"})
        return out, out[0]["z"] is not None

    def detr(self, key, query_en):
        from ai.features.run_moment_detr_inference import predict_moments_hybrid
        r = predict_moments_hybrid(video_id=f"bench_{key}", video_feature_path=str(self.feature_path(key)), query=query_en, top_k=10)
        scores = [float(x["score"]) for x in r]
        out = [{"start_time": float(x["start_time"]), "end_time": float(x["end_time"]), "score": s,
                "z": zscore_of(s, scores, self.captions.ZSCORE_MIN_WINDOWS, self.captions.ZSCORE_MIN_STD), "source": "detr"}
               for x, s in zip(r, scores)]
        return out, bool(out) and out[0]["z"] is not None


# ===================== 합치기 =====================

def fuse(sub, cap, third, duration, widen, expand, overlap):
    """sub/cap/third: (후보 목록, z 사용 가능) 또는 None. captions.fused_search와 같은 규칙에 세 번째 신호를 더함."""
    have_sub = bool(sub and sub[0])
    cap_l, cap_ok = cap
    if have_sub:
        sub_l, sub_ok = sub
        if not (sub_ok and cap_ok):           # 서비스: 자막 우선(z 불가)
            order = [sub_l, cap_l]
            rule = "subtitle_first(z불가)"
        else:
            order = sorted([sub_l, cap_l], key=lambda l: -l[0]["z"])
            rule = "zscore_max"
    else:
        order = [cap_l]
        rule = "caption_only"
    if third and third[0]:
        t_l, t_ok = third
        if rule == "zscore_max" or (rule == "caption_only" and cap_ok):
            if t_ok:
                srcs = order + [t_l]
                order = sorted(srcs, key=lambda l: -l[0]["z"])
            else:
                order = order + [t_l]
        else:
            order = order + [t_l]

    def span(m):
        if m["source"] == "subtitle":
            return widen([{"start_time": m["start_time"], "end_time": m["end_time"], "source": "subtitle"}])[0]
        if m["source"] == "caption":
            return {"start_time": round(max(0.0, m["start_time"] - expand), 2),
                    "end_time": round(min(duration, m["end_time"] + expand), 2)}
        return {"start_time": round(m["start_time"], 2), "end_time": round(m["end_time"], 2)}

    merged, idx = [], [0] * len(order)
    while len(merged) < TOP_K and any(idx[j] < len(order[j]) for j in range(len(order))):
        for j in range(len(order)):
            while idx[j] < len(order[j]):
                m = order[j][idx[j]]
                idx[j] += 1
                c = {**{k: v for k, v in span(m).items() if k in ("start_time", "end_time")},
                     "score": round(float(m["score"]), 4), "source": m["source"]}
                if all(overlap(c, k) < 0.5 for k in merged):
                    merged.append(c)
                    break
            if len(merged) >= TOP_K:
                break
    return merged, rule


# ===================== 실행 =====================

def run(a):
    import query_set

    from backend.services import captions
    from backend.services.search_api import _widen_subtitle
    from backend.services.subtitles import load_subtitles
    from backend.services.translate import to_english

    qs = query_set.load(Path(a.queries).expanduser(), subset=a.subset)
    sig = Signals(a.features)
    expand = sig.cfg["expand"]

    # fused_search의 자막 창 임베딩 캐시는 data/processed/에 파일을 쓰므로, 같은 계산을 저장 없이 하도록 바꿈
    def no_save_embeddings(youtube_video_id, wins, model):
        return model.encode([w["text"] for w in wins], convert_to_tensor=True).float().cpu()
    captions._subtitle_embeddings = no_save_embeddings

    rows, timing, mismatch = [], {"clip": [], "detr": [], "translate": []}, []
    for num, key, typ, query, gts in qs.queries:
        yid = qs.videos[key]["youtube_id"]
        index = captions.load_index(yid)
        if index is None:
            raise SystemExit(f"{yid}: 설명문 파일 없음")
        duration = float(index["meta"]["duration"])
        subtitles, lang = load_subtitles(yid)
        subtitles = subtitles if (lang == "ko" and subtitles) else []
        sub = sig.subtitle(yid, subtitles, query) if subtitles else None
        cap = sig.caption(index, query)
        t = time.perf_counter(); clip = sig.clip(key, duration, query); timing["clip"].append(time.perf_counter() - t)
        t = time.perf_counter(); en = to_english(query); timing["translate"].append(time.perf_counter() - t)
        t = time.perf_counter(); detr = sig.detr(key, en); timing["detr"].append(time.perf_counter() - t)
        res = {}
        for name, third in (("a", None), ("b", clip), ("c", detr)):
            merged, rule = fuse(sub, cap, third, duration, _widen_subtitle, expand, captions._overlap)
            res[name] = {"moments": merged, "rule": rule}
        # (a)가 서비스 함수(captions.fused_search)와 같은지 확인
        fs = captions.fused_search(yid, query, TOP_K, subtitles, index, _widen_subtitle, sig.minilm, threading.Lock())
        if [(m["start_time"], m["end_time"], m["source"]) for m in fs] != \
           [(m["start_time"], m["end_time"], m["source"]) for m in res["a"]["moments"]]:
            mismatch.append(num)
        # 탐색적: 신호 하나만 쓸 때의 상위 5개 (구간 규칙은 합칠 때와 같음)
        alone = {}
        for name, lst in (("subtitle", sub[0] if sub else []), ("caption", cap[0]), ("clip", clip[0]), ("detr", detr[0])):
            alone[name] = {"moments": fuse(None, (lst, False), None, duration, _widen_subtitle, expand, captions._overlap)[0]} \
                if lst else {"moments": []}
        res.update({f"only_{k}": v for k, v in alone.items()})
        rows.append({"num": num, "video": key, "youtube_id": yid, "type": typ, "query": query, "query_en": en,
                     "gt": [list(g) for g in gts], **qs.info[num], "has_subtitles": bool(subtitles), **res,
                     "top_z": {"subtitle": sub[0][0]["z"] if sub and sub[0] else None, "caption": cap[0][0]["z"],
                               "clip": clip[0][0]["z"] if clip[0] else None, "detr": detr[0][0]["z"] if detr[0] else None}})
        print(f"#{num} {typ} a={res['a']['moments'][0]['source']} b={res['b']['moments'][0]['source']} "
              f"c={res['c']['moments'][0]['source']}", flush=True)
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    meta = {"queries": str(a.queries), "subset": a.subset, "features": str(a.features), "device": "cpu",
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "top_k": TOP_K, "expand": expand,
            "timing_ms_mean": {k: round(1000 * sum(v) / len(v), 1) for k, v in timing.items() if v},
            "a_vs_fused_search_mismatch": mismatch}
    print(f"(a) vs captions.fused_search: {len(rows)}개 중 다른 질의 {len(mismatch)}개 {mismatch}")
    (out / "results.json").write_text(json.dumps({"meta": meta, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("저장:", out / "results.json")


def check_api(path, base):
    """(a) 결과를 실제 서비스 검색 결과와 비교 (서비스가 떠 있을 때)."""
    import requests
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    diff = []
    for r in data["rows"]:
        d = requests.post(f"{base}/api/search", json={"youtube_video_id": r["youtube_id"], "query": r["query"], "top_k": TOP_K},
                          timeout=120).json()
        api = [(round(m["start_time"], 2), round(m["end_time"], 2), m.get("source")) for m in d.get("results", [])]
        mine = [(round(m["start_time"], 2), round(m["end_time"], 2), m["source"]) for m in r["a"]["moments"]]
        if api != mine:
            diff.append(r["num"])
    print(f"(a) vs 서비스: {len(data['rows'])}개 중 다른 질의 {len(diff)}개 {diff}")


# ===================== 집계 =====================

def report(path):
    import summary
    data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    with open(SCOPE_TSV, encoding="utf-8") as f:
        scope = {int(r["num"]): r["scope"] for r in csv.DictReader(f, delimiter="\t")}

    def metrics(r, m):
        gts = [tuple(g) for g in r["gt"]]
        segs = [(x["start_time"], x["end_time"]) for x in r[m]["moments"]]
        if not segs:
            return 0, 0, 0
        top1 = segs[0]
        iou = summary.best_iou(top1, gts)
        r3 = any(summary.best_iou(s, gts) >= 0.3 for s in summary.nms_top(segs))
        mid = (top1[0] + top1[1]) / 2
        hit = any(a <= mid <= b for a, b in gts)
        return int(iou >= 0.3), int(r3), int(hit)

    groups = [("전체", lambda r: True)]
    for sc in ("넓은 장면", "특정 순간"):
        groups.append((sc, lambda r, sc=sc: scope[r["num"]] == sc))
        for t in ("S", "V"):
            groups.append((f"{sc} · {t}", lambda r, sc=sc, t=t: scope[r["num"]] == sc and r["type"] == t))
    rows = data["rows"]
    print("| 묶음 (질의 수) | (a) 현재 서비스 | (b) a + 다국어 CLIP | (c) a + Moment-DETR |")
    print("|---|---|---|---|")
    for name, fn in groups:
        rs = [r for r in rows if fn(r)]
        if not rs:
            continue
        cells = []
        for m in ("a", "b", "c"):
            v = [metrics(r, m) for r in rs]
            cells.append(" / ".join(str(sum(x[i] for x in v)) for i in range(3)))
        print(f"| {name} ({len(rs)}) | " + " | ".join(cells) + " |")
    print("\n각 칸: IoU≥0.3 / R@3 / hit-in-GT (개수)")
    if "only_clip" in rows[0]:
        print("\n탐색적: 신호 하나만 쓸 때 (자막 없는 영상의 자막 칸은 결과 없음 = 0)")
        names = [("only_subtitle", "자막만"), ("only_caption", "설명문만"), ("only_clip", "다국어 CLIP만"), ("only_detr", "Moment-DETR만")]
        print("| 묶음 (질의 수) | " + " | ".join(n for _, n in names) + " |")
        print("|---|" + "---|" * len(names))
        for name, fn in groups:
            rs = [r for r in rows if fn(r)]
            cells = []
            for m, _ in names:
                v = [metrics(r, m) for r in rs]
                cells.append(" / ".join(str(sum(x[i] for x in v)) for i in range(3)))
            print(f"| {name} ({len(rs)}) | " + " | ".join(cells) + " |")
        import statistics as st
        print("\n1위 후보 z-score 중앙값 (범위)")
        for src in ("subtitle", "caption", "clip", "detr"):
            zs = [r["top_z"][src] for r in rows if r["top_z"][src] is not None]
            if zs:
                print(f"- {src}: {st.median(zs):.2f} ({min(zs):.2f}~{max(zs):.2f}), z 계산 가능 {len(zs)}/{len(rows)}")
    for m in ("b", "c"):
        firsts = sum(1 for r in rows if r[m]["moments"][0]["source"] in ("clip", "detr"))
        changed = [r["num"] for r in rows if r[m]["moments"][0] != r["a"]["moments"][0]]
        print(f"({m}) 1위가 세 번째 신호인 질의 {firsts}개, 1위가 (a)와 다른 질의 {len(changed)}개 {changed}")
    print("평균 시간(ms, CPU):", data["meta"]["timing_ms_mean"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries")
    ap.add_argument("--subset", default="dev")
    ap.add_argument("--features")
    ap.add_argument("--out")
    ap.add_argument("--report")
    ap.add_argument("--check-api", nargs=2, metavar=("RESULTS", "BASE_URL"))
    a = ap.parse_args()
    if a.report:
        report(a.report)
    elif a.check_api:
        check_api(*a.check_api)
    else:
        run(a)


if __name__ == "__main__":
    main()
