"""학습한 구간 검색 모델(CLIP 재현·VLM 변형)을 복지 dev에서 평가. **dev만** (test는 이 스크립트로 돌릴 수 없음).

추론은 서비스 predict_moments(ai/features/run_moment_detr_inference.py)와 같은 방식: 영상 전체 특징 + TEF, L2 정규화,
점수 = softmax(pred_logits)[...,0], 구간 = span_cxw_to_xx × (칸 수 × 2초).
- clip_repro: CLIP 2초 특징(eval_features/clip) + NLLB 번역 영어 질의의 CLIP 텍스트 토큰 (서비스와 같음)
- vlm_*: Qwen3-VL-Embedding-2B 2초 특징(eval_features/qwen_640) + 한국어 질의 그대로 (tok 또는 pooled)
지표는 예비 실험과 같은 형식으로 저장 → prelim_report.py로 표.

    python ai/experiments/vlm_model/mr_eval_dev.py --root <mr_runs 폴더> --out <폴더>
"""
import argparse, json, statistics, sys, time
from pathlib import Path

import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "backend/services"), str(ROOT / "ai/experiments/translation_compare"),
                str(Path(__file__).parent), str(ROOT / "ai/vendor/moment_detr")]
DATA = Path("/nfs/team/data/scenefinder_vlm")
CLIP_LEN = 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--models", help="쉼표로 구분 (기본: state의 모든 학습 변형)")
    a = ap.parse_args()
    import summary
    from prelim_eval import load_queries
    from run_on_video.model_utils import build_inference_model
    from utils.tensor_utils import pad_sequences_1d
    from moment_detr.span_utils import span_cxw_to_xx

    videos, pos, neg, _ = load_queries(include_unreviewed=False)
    dev = {k: v for k, v in videos.items() if v["split"] == "dev"}
    assert all(q["video"] in dev for q in pos + neg) and all(v["split"] == "dev" for v in dev.values())
    states = {p.stem: json.loads(p.read_text()) for p in sorted((Path(a.root) / "state").glob("*.json"))
              if p.stem != "selected_text_feat"}
    names = a.models.split(",") if a.models else list(states)
    print(f"dev 질의 {len(pos)} + 정답 없음 {len(neg)}, 모델 {names}", flush=True)

    nllb = clipx = qenc = None
    vf_cache, q_cache = {}, {}

    def vfeat(k, kind):
        key = (k, kind)
        if key not in vf_cache:
            yid = dev[k]["youtube_id"]
            p = DATA / "eval_features" / ("clip" if kind == "clip" else "qwen_640") / (f"{yid}_clip_features.pt" if kind == "clip" else f"{yid}.pt")
            v = F.normalize(torch.load(p, map_location="cuda").float(), dim=-1, eps=1e-5)
            n = len(v); st = torch.arange(n, device="cuda", dtype=torch.float32) / n
            vf_cache[key] = (torch.cat([v, torch.stack([st, st + 1.0 / n], 1)], 1)[None], n)
        return vf_cache[key]

    def qfeat(q, kind):
        nonlocal nllb, clipx, qenc
        key = (q, kind)
        if key not in q_cache:
            if kind == "clip":
                if nllb is None:
                    from translate import to_english
                    from ai.features.run_moment_detr_inference import get_feature_extractor
                    nllb, clipx = to_english, get_feature_extractor()
                feats = clipx.encode_text([nllb(q)])
            else:
                if qenc is None:
                    from qvh_text_features import TextEncoder
                    qenc = TextEncoder()
                tok, pooled = qenc.encode([q])[0]
                feats = [torch.from_numpy(tok if kind == "tok" else pooled).float()]
            f, m = pad_sequences_1d(feats, dtype=torch.float32, device="cuda", fixed_length=None)
            q_cache[key] = (F.normalize(f, dim=-1, eps=1e-5), m)
        return q_cache[key]

    rows = {q["num"]: {k: q[k] for k in ("num", "video", "type", "query", "gt", "origin", "partial")} | {"overlay_text": bool(q.get("overlay_text"))} for q in pos}
    negs = {q["num"]: {"num": q["num"], "video": q["video"], "query": q["query"], "origin": q["origin"]} for q in neg}
    lat = {}
    for name in names:
        s = states[name]
        model = build_inference_model(str(Path(s["run_dir"]) / "model_best.ckpt")).cuda().eval()
        vkind = "clip" if name == "clip_repro" else "qwen"
        tkind = "clip" if name == "clip_repro" else name.split("_")[1]
        lat[name] = []
        for q in pos + neg:
            torch.cuda.synchronize(); t0 = time.time()
            v, n = vfeat(q["video"], vkind); t, tm = qfeat(q["query"], tkind)
            with torch.no_grad():
                o = model(src_vid=v, src_vid_mask=torch.ones(1, n, device="cuda"), src_txt=t, src_txt_mask=tm)
            sc = F.softmax(o["pred_logits"], -1)[0, :, 0].cpu()
            dur = n * CLIP_LEN
            spans = (span_cxw_to_xx(o["pred_spans"][0].cpu()) * dur).clamp(0, dur)
            order = torch.argsort(sc, descending=True).tolist()
            ranked = [(float(spans[i, 0]), float(max(spans[i, 1], spans[i, 0]))) for i in order]
            torch.cuda.synchronize(); lat[name].append(time.time() - t0)
            if q["num"] in rows:
                top = summary.nms_top(ranked, k=5)
                rows[q["num"]][name] = {"top5": top, "iou": summary.best_iou(top[0], q["gt"]) if top else 0.0, "score": float(sc[order[0]])}
            else:
                negs[q["num"]][name] = float(sc[order[0]])
        del model; torch.cuda.empty_cache()
        print(f"{name}: R@1 IoU>=0.3 {sum(r[name]['iou'] >= 0.3 for r in rows.values())}/{len(rows)}", flush=True)
    # 무작위 기준선은 예비 실험 결과에서 가져옴 (같은 질의·같은 seed)
    prelim = {r["num"]: r for r in json.loads((ROOT / "ai/experiments/vlm_model/results/prelim_dev/rows.json").read_text())}
    for num, r in rows.items():
        r["random"] = prelim[num]["random"] if num in prelim else {"iou_mean": 0, "p03": 0, "p05": 0}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "rows.json").write_text(json.dumps(list(rows.values()), ensure_ascii=False, indent=1))
    (out / "negatives.json").write_text(json.dumps(list(negs.values()), ensure_ascii=False, indent=1))
    meta = {"methods": names, "latency_sec": {n: {"median": round(statistics.median(v), 4), "p95": round(sorted(v)[int(0.95 * (len(v) - 1))], 4)} for n, v in lat.items()},
            "gpu_peak_gib_during_queries": round(torch.cuda.max_memory_allocated() / 2**30, 2),
            "extraction_sec_per_video_min": json.loads((ROOT / "ai/experiments/vlm_model/results/prelim_dev/meta.json").read_text())["extraction_sec_per_video_min"]}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"→ {out}")


if __name__ == "__main__":
    main()
