"""11/14 예비 실험: dev 학습 없는 기준값 (설정은 docs/experiments/vlm_model_plan.md 「11/14 예비 실험」에 결과 전 고정).

방식
- B1 자막 검색: 파인튜닝 MiniLM, 1~3문장 자막 창, 서비스 구간 보정(시작 2초 앞당김·최소 6초)
- B2 구간 검색 CLIP 버전: NLLB 한→영 번역 + Moment-DETR(predict_moments_hybrid, 서비스와 같이 자막 경로 없이)
- B3 main 서비스 결합: 서비스 predict_moments와 같은 순서 (한국어 자막이 있으면 MiniLM 결과만, 없으면 B2), 보정·중복 제거 포함
- F-CLIP / F-VLM(640) / F-VLM-1280(참고): 프레임 유사도 → 평활화 → 상위 8칸 → 가장 긴 연속 구간 (eval_v2 (c)와 같은 규칙)
- REF-SUB-VLM(참고): 자막 검색을 Qwen3-VL-Embedding 텍스트로 (B1과 같은 창·보정)

질의: review.json의 dev 영상, 검수 완료(human_reviewed)만. 출처(origin)는 ai_draft / simulated_user. 검수 중 새로 만든
질의는 문구를 vlm_eval_sim_queries.json과 맞춰 simulated_user로 되살린다.

    python ai/experiments/vlm_model/prelim_eval.py --dry-run       # 개수·경로만 확인 (지표 출력 안 함)
    python ai/experiments/vlm_model/prelim_eval.py --out ai/experiments/vlm_model/results/prelim_dev
"""
import argparse, json, os, random, statistics, sys, time
from pathlib import Path

import torch
import torch.nn.functional as F
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "backend" / "services"), str(ROOT / "ai/experiments/translation_compare"),
                str(Path(__file__).parent)]
load_dotenv(ROOT / "backend" / ".env")
DATA = Path("/nfs/team/data/scenefinder_vlm")
LABELS = ROOT / "ai/experiments/vlm_model/labels/review.json"
SIM = ROOT / "docs/experiments/vlm_eval_sim_queries.json"
PAD_BEFORE, MIN_LEN = 2.0, 6.0          # 서비스 SUBTITLE_PAD_BEFORE / SUBTITLE_MIN_LEN 기본값
TOP_K_SERVICE = 5
QWEN_Q_INSTR = "Retrieve images or video frames relevant to the user's query."
RANDOM_SEED, RANDOM_SAMPLES = 0, 100
LORA = {"adapter": None, "feats": None}   # --lora: 화면 검색 LoRA 적용본 평가 (질의 인코더 + dev 프레임 특징을 LoRA 모델 것으로)
METHODS = ["B1", "B2", "B3", "F-CLIP", "F-VLM", "F-VLM-1280", "REF-SUB-VLM"]


def load_queries(include_unreviewed):
    data = json.loads(LABELS.read_text(encoding="utf-8"))
    sim_texts = {q["query"]: q for qs in json.loads(SIM.read_text())["queries"].values() for q in qs}
    dev = {k for k, v in data["videos"].items() if v["split"] == "dev"}
    ok = lambda q: q["video"] in dev and (include_unreviewed or q.get("source") == "human_reviewed")  # noqa: E731

    def origin(q):
        if q.get("origin"):
            return q["origin"]
        return "simulated_user" if q["query"] in sim_texts else "manual"

    pos = [{**q, "origin": origin(q), "partial": str(q.get("note", "")).startswith("부분")} for q in data["queries"] if ok(q)]
    neg = [{**q, "origin": origin(q)} for q in data.get("negative_queries", []) if ok(q)]
    return data["videos"], pos, neg, sim_texts


def widen(seg):
    s = max(0.0, seg[0] - PAD_BEFORE)
    return (round(s, 2), round(max(seg[1], s + MIN_LEN), 2))


def service_dedupe(moments, top_k, thr=0.5):
    """backend/services/search_api.py _dedupe와 같음 (겹친 길이 / 더 짧은 구간)."""
    kept = []
    for m in moments:
        ok = True
        for k in kept:
            inter = max(0.0, min(m[1], k[1]) - max(m[0], k[0])); short = min(m[1] - m[0], k[1] - k[0])
            if short > 0 and inter / short >= thr:
                ok = False; break
        if ok:
            kept.append(m)
        if len(kept) == top_k:
            break
    return kept


class Methods:
    def __init__(self, videos):
        from ai.features.fusion_search import get_semantic_model, get_semantic_subtitle_candidates
        from ai.features.run_moment_detr_inference import (CLIP_LEN, VISUAL_TOP_K, _make_contiguous_clusters,
                                                           _smooth_scores, predict_moments_hybrid)
        self.videos = videos
        self.minilm = get_semantic_model("finetuned"); self.sub_cands = get_semantic_subtitle_candidates
        self.hybrid = predict_moments_hybrid
        self.CLIP_LEN, self.TOPK, self.clusters, self.smooth = CLIP_LEN, VISUAL_TOP_K, _make_contiguous_clusters, _smooth_scores
        self.subs, self.vfeat = {}, {}
        for k, v in videos.items():
            yid = v["youtube_id"]
            sub = json.loads((DATA / "eval_subtitles" / f"{yid}.json").read_text())
            self.subs[k] = (sub["segments"], sub["language"])
            self.vfeat[k] = {"clip": DATA / "eval_features/clip" / f"{yid}_clip_features.pt",
                             "qwen_640": (Path(LORA["feats"]) if LORA["feats"] else DATA / "eval_features/qwen_640") / f"{yid}.pt",
                             "qwen_1280": DATA / "eval_features/qwen_1280" / f"{yid}.pt"}
        self._nllb = self._mclip = self._qwen = None
        self._featcache = {}

    # ---------- 자막 ----------
    def _sub_ranked(self, k, q, encoder="minilm"):
        segs, _ = self.subs[k]
        if not segs:
            return []
        if encoder == "minilm":
            cands = self.sub_cands(query=q, subtitles=segs, model=self.minilm, top_k=10**6)
        else:
            cands = self._qwen_sub_cands(q, segs)
        return [(float(c["start_time"]), float(c["end_time"]), float(c["score"])) for c in cands]

    def B1(self, k, q):
        return [widen(c[:2]) for c in self._sub_ranked(k, q)]

    def REF_SUB_VLM(self, k, q):
        return [widen(c[:2]) for c in self._sub_ranked(k, q, "qwen")]

    # ---------- 번역 + Moment-DETR ----------
    def _en(self, q):
        if self._nllb is None:
            from translate import to_english   # backend/services/translate.py (서비스 기본값 NLLB)
            self._nllb = to_english
        return self._nllb(q)

    def B2(self, k, q, top_k=TOP_K_SERVICE * 3):
        r = self.hybrid(video_id=f"vlm_{k}", video_feature_path=str(self.vfeat[k]["clip"]), query=self._en(q), top_k=top_k)
        return [(float(x["start_time"]), float(x["end_time"])) for x in r]

    def B3(self, k, q):
        segs, lang = self.subs[k]
        if lang == "ko" and segs:   # 서비스: predict_moments_fusion(top_k*3) → 자막 구간 보정 → 중복 제거(top_k)
            from ai.features.fusion_search import predict_moments_fusion
            raw = predict_moments_fusion(video_id=f"vlm_{k}", feature_path=str(self.vfeat[k]["clip"]), subtitles=segs,
                                         korean_query=q, english_query="", video_duration=None,
                                         top_k=TOP_K_SERVICE * 3, model_type="finetuned")
            if raw:
                m = [widen((r["start_time"], r["end_time"])) if r.get("source") == "subtitle"
                     else (float(r["start_time"]), float(r["end_time"])) for r in raw]
                return service_dedupe(m, TOP_K_SERVICE)
        return service_dedupe(self.B2(k, q), TOP_K_SERVICE)

    # ---------- 화면 검색 ----------
    def _feat(self, k, kind):
        key = (k, kind)
        if key not in self._featcache:
            self._featcache[key] = F.normalize(torch.load(self.vfeat[k][kind], map_location="cpu").float(), dim=-1)
        return self._featcache[key]

    def _qwen_text(self, texts, instr):
        if self._qwen is None:
            import speed_opt
            self._qwen = speed_opt.Embedder()
            if LORA["adapter"]:
                from lora import load_lora
                load_lora(self._qwen.m, LORA["adapter"])
        p = self._qwen.proc["torchvision"]
        msgs = [[{"role": "system", "content": [{"type": "text", "text": instr}]},
                 {"role": "user", "content": [{"type": "text", "text": t}]}] for t in texts]
        out = []
        with torch.no_grad():
            for i in range(0, len(msgs), 32):
                txt = p.apply_chat_template(msgs[i:i + 32], add_generation_prompt=True, tokenize=False)
                x = p(text=txt, padding=True, return_tensors="pt").to("cuda")
                h = self._qwen.m(**x).last_hidden_state
                last = x["attention_mask"].sum(1) - 1
                out.append(F.normalize(h[torch.arange(h.shape[0], device=h.device), last].float(), dim=-1).cpu())
        return torch.cat(out)

    def _qwen_sub_cands(self, q, segs):
        windows = [(segs[i]["start_time"], segs[i + s - 1]["end_time"], " ".join(x["text"] for x in segs[i:i + s]))
                   for s in (1, 2, 3) for i in range(len(segs) - s + 1)]
        ck = ("subwin", id(segs))
        if ck not in self._featcache:
            self._featcache[ck] = self._qwen_text([w[2] for w in windows], "Represent the user's input.")
        sc = self._featcache[ck] @ self._qwen_text([q], "Retrieve subtitle passages relevant to the user's query.")[0]
        return [{"start_time": windows[i][0], "end_time": windows[i][1], "score": float(sc[i])}
                for i in torch.argsort(sc, descending=True).tolist()]

    def _frame_rank(self, k, qv, kind):
        vf = self._feat(k, kind)
        smoothed = self.smooth(vf @ qv)
        dur = self.videos[k]["duration"]
        top = torch.topk(smoothed, k=min(self.TOPK, len(smoothed))).indices.tolist()
        multi = [c for c in self.clusters(top) if len(c) >= 2]
        span = lambda c: (float(min(c) * self.CLIP_LEN), float(min((max(c) + 1) * self.CLIP_LEN, dur)))  # noqa: E731
        ranked = sorted(multi, key=lambda c: (len(c), float(smoothed[c].mean())), reverse=True)
        best = ranked[0] if ranked else [int(torch.argmax(smoothed))]
        ranked += [[i] for i in torch.argsort(smoothed, descending=True).tolist()]
        return [span(best)] + [span(c) for c in ranked], float(smoothed[best].mean())

    def F_CLIP(self, k, q):
        if self._mclip is None:
            from sentence_transformers import SentenceTransformer
            self._mclip = SentenceTransformer("sentence-transformers/clip-ViT-B-32-multilingual-v1", device="cuda")
        qv = F.normalize(torch.tensor(self._mclip.encode([q]))[0].float(), dim=-1)
        return self._frame_rank(k, qv, "clip")[0]

    def F_VLM(self, k, q, kind="qwen_640"):
        qv = self._qwen_text([q], QWEN_Q_INSTR)[0]
        return self._frame_rank(k, qv, kind)[0]

    def F_VLM_1280(self, k, q):
        return self.F_VLM(k, q, "qwen_1280")

    def run(self, name, k, q):
        return getattr(self, name.replace("-", "_"))(k, q)

    def top1_score(self, name, k, q):
        """정답 없음 질의용: 1위 점수 (방식마다 척도가 다름)."""
        if name in ("B1", "REF-SUB-VLM"):
            r = self._sub_ranked(k, q, "minilm" if name == "B1" else "qwen")
            return r[0][2] if r else None
        if name.startswith("F-"):
            if name == "F-CLIP":
                self.F_CLIP(k, q)  # 모델 준비
                qv = F.normalize(torch.tensor(self._mclip.encode([q]))[0].float(), dim=-1)
                return self._frame_rank(k, qv, "clip")[1]
            qv = self._qwen_text([q], QWEN_Q_INSTR)[0]
            return self._frame_rank(k, qv, "qwen_1280" if name.endswith("1280") else "qwen_640")[1]
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--lora", help="LoRA 어댑터(adapter.pt). 같은 폴더의 dev_qwen_640 특징을 씀 (F-VLM만 의미 있음)")
    a = ap.parse_args()
    if a.lora:
        LORA["adapter"] = a.lora; LORA["feats"] = str(Path(a.lora).parent / "dev_qwen_640")
    import summary   # eval_v2 지표: iou, best_iou, nms_top(IoU 0.5), start_ok(±5초)
    videos, pos, neg, sim_texts = load_queries(include_unreviewed=a.dry_run)
    dev_videos = {k: v for k, v in videos.items() if v["split"] == "dev"}
    print(f"dev 영상 {len(dev_videos)}, 정답 있는 질의 {len(pos)} (사용자 질문 {sum(q['origin'] == 'simulated_user' for q in pos)}), "
          f"정답 없음 {len(neg)}" + (" [dry-run: 미검수 포함, 지표 출력 안 함]" if a.dry_run else ""))
    for k, v in dev_videos.items():
        f = [DATA / "eval_features/clip" / f"{v['youtube_id']}_clip_features.pt",
             (Path(LORA["feats"]) if LORA["feats"] else DATA / "eval_features/qwen_640") / f"{v['youtube_id']}.pt",
             DATA / "eval_subtitles" / f"{v['youtube_id']}.json"]
        assert all(p.exists() for p in f), f"{k}: 파일 없음 {[str(p) for p in f if not p.exists()]}"
    m = Methods(dev_videos)
    methods = a.methods.split(",")
    rows, lat = [], {n: [] for n in methods}
    torch.cuda.reset_peak_memory_stats()
    for q in pos:
        row = {k: q[k] for k in ("num", "video", "type", "query", "gt", "origin", "partial")}
        row["overlay_text"] = bool(q.get("overlay_text"))
        for n in methods:
            torch.cuda.synchronize(); t0 = time.time()
            ranked = m.run(n, q["video"], q["query"])
            torch.cuda.synchronize(); lat[n].append(time.time() - t0)
            top = summary.nms_top(ranked, k=5) if ranked else []
            row[n] = {"top5": top, "iou": summary.best_iou(top[0], q["gt"]) if top else 0.0,
                      "score": None if a.dry_run else m.top1_score(n, q["video"], q["query"])}
        rows.append(row)
        if a.dry_run and len(rows) >= 3:
            break
    neg_rows = []
    for q in ([] if a.dry_run else neg):
        neg_rows.append({"num": q["num"], "video": q["video"], "query": q["query"], "origin": q["origin"],
                         **{n: m.top1_score(n, q["video"], q["query"]) for n in methods}})
    if a.dry_run:
        print("dry-run 통과: 방식", methods, "질의 3개 실행, 지연(초)", {n: round(statistics.median(v), 3) for n, v in lat.items()})
        return
    # 무작위 기준선: 영상별 정답 평균 길이 구간을 무작위 위치에 100번
    rng = random.Random(RANDOM_SEED)
    for r in rows:
        dur = dev_videos[r["video"]]["duration"]; L = statistics.mean(e - s for s, e in r["gt"])
        sims = [summary.best_iou((s, s + L), r["gt"]) for s in (rng.uniform(0, max(0.0, dur - L)) for _ in range(RANDOM_SAMPLES))]
        r["random"] = {"iou_mean": statistics.mean(sims), "p03": sum(x >= 0.3 for x in sims) / len(sims),
                       "p05": sum(x >= 0.5 for x in sims) / len(sims)}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    timing = json.loads((DATA / "eval_features/timing.json").read_text())
    meta = {"methods": methods, "lora": a.lora, "n_pos": len(rows), "n_neg": len(neg_rows),
            "latency_sec": {n: {"median": round(statistics.median(v), 4), "p95": round(sorted(v)[int(0.95 * (len(v) - 1))], 4)} for n, v in lat.items()},
            "gpu_peak_gib_during_queries": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            "extraction_sec_per_video_min": {kind: round(sum(t[kind]["sec"] for k, t in timing.items() if k in dev_videos and kind in t) /
                                                         sum(t[kind]["video_sec"] for k, t in timing.items() if k in dev_videos and kind in t) * 60, 3)
                                             for kind in ("qwen_640", "qwen_1280")}}
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (out / "negatives.json").write_text(json.dumps(neg_rows, ensure_ascii=False, indent=1))
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"→ {out}  (집계: prelim_report.py)")


if __name__ == "__main__":
    main()
