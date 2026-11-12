"""시연용 영상 미리 분석 → /nfs/team/data/scenefinder_vlm/demo/index/<유튜브ID>/ + backend/data/demo_videos.json(목록)

영상마다:
  subs.json     자막 (서비스와 같은 Whisper large-v3-turbo, 말이 거의 없으면 빈 목록)
  lora_640.pt   화면 검색 특징: Qwen3-VL-Embedding-2B + 고른 LoRA(welfare ep1), 2초 칸, 640×360 (평가와 같은 디코딩)
  frames.npy    2초 칸 프레임 640×360 (VLM 재판별용, 질의 때 디코딩하지 않게)
  clip.pt       CLIP 특징 (main 방식용, 서비스 build_feature)
dev 영상은 평가 때 만든 같은 파일을 복사한다(같은 설정). test 영상은 test 실행 뒤에만 추가(--include-test, 지금은 막아 둠).
LoRA 학습 영상은 넣지 않는다(시연 결과가 실제보다 좋아 보이지 않게, 2026-11-12 결정).

    python backend/scripts/index_demo.py
"""
import argparse, csv, json, math, os, shutil, sys, time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend/services"), str(ROOT / "ai/experiments/vlm_model")]
os.environ.setdefault("WHISPER_MODEL_SIZE", "large-v3-turbo")
D = Path("/nfs/team/data/scenefinder_vlm")
IDX = D / "demo/index"
NEW_VIDEOS = D / "demo/videos"
LORA = D / "lora_runs/welfare/ep1"
CATALOG = ROOT / "backend/data/demo_videos.json"
CLIP_LEN = 2


def rows():
    out = []
    lora_ids = {r["youtube_id"] for r in csv.DictReader(open(ROOT / "docs/experiments/vlm_lora_train_videos.tsv"), delimiter="\t")}
    cand = {r["youtube_id"]: r for f in ("vlm_eval_candidates.tsv", "vlm_lora_candidates.tsv")
            for r in csv.DictReader(open(ROOT / "docs/experiments" / f), delimiter="\t")}
    for r in csv.DictReader(open(ROOT / "docs/experiments/vlm_eval_split.tsv"), delimiter="\t"):
        if r["split"] != "dev":
            continue
        out.append({"youtube_id": r["youtube_id"], "title": r["title"], "channel": r["channel"], "policy_hint": r["policy"],
                    "published": cand.get(r["youtube_id"], {}).get("published", ""), "duration_sec": int(float(r["duration_sec"])),
                    "origin": "eval_dev", "video_path": str(D / "eval_videos" / f"{r['youtube_id']}.mp4")})
    for r in csv.DictReader(open(ROOT / "docs/service/demo_new_videos.tsv"), delimiter="\t"):
        out.append({"youtube_id": r["youtube_id"], "title": r["title"], "channel": r["channel"], "policy_hint": r["policy"],
                    "published": r["published"], "duration_sec": int(r["duration_sec"]), "origin": "demo_new",
                    "video_path": str(NEW_VIDEOS / f"{r['youtube_id']}.mp4")})
    test_ids = {r["youtube_id"] for r in csv.DictReader(open(ROOT / "docs/experiments/vlm_eval_split.tsv"), delimiter="\t") if r["split"] == "test"}
    assert not ({r["youtube_id"] for r in out} & (lora_ids | test_ids)), "LoRA 학습 영상·test 영상은 시연 목록에 넣지 않음"
    return out


def main():
    ap = argparse.ArgumentParser(); ap.parse_args()
    items = [r for r in rows() if Path(r["video_path"]).exists()]
    print(f"시연 영상 {len(items)}개 (받은 것만)", flush=True)
    for r in items:
        (IDX / r["youtube_id"]).mkdir(parents=True, exist_ok=True)
    # 1) dev: 평가 때 만든 파일 복사 (같은 설정)
    for r in items:
        if r["origin"] != "eval_dev":
            continue
        y, d = r["youtube_id"], IDX / r["youtube_id"]
        for src, dst in [(D / "eval_subtitles" / f"{y}.json", d / "subs.json"), (LORA / "dev_qwen_640" / f"{y}.pt", d / "lora_640.pt"),
                         (D / "eval_frames_640" / f"{y}.npy", d / "frames.npy"), (D / "eval_features/clip" / f"{y}_clip_features.pt", d / "clip.pt")]:
            if not dst.exists():
                shutil.copy(src, dst)
    new = [r for r in items if r["origin"] == "demo_new"]
    # 2) 새 영상 자막
    todo = [r for r in new if not (IDX / r["youtube_id"] / "subs.json").exists()]
    if todo:
        from subtitles import _transcribe, MIN_SUBTITLE_SEGMENTS, MIN_SUBTITLE_CHARS
        for r in todo:
            items_, lang, prob = _transcribe(r["video_path"])
            if len(items_) < MIN_SUBTITLE_SEGMENTS or sum(len(i["text"]) for i in items_) < MIN_SUBTITLE_CHARS:
                items_ = []
            (IDX / r["youtube_id"] / "subs.json").write_text(json.dumps({"source": "whisper_large-v3-turbo", "language": lang,
                                                                        "segments": items_}, ensure_ascii=False, indent=1))
            print("자막", r["youtube_id"], len(items_), flush=True)
        del _transcribe; torch.cuda.empty_cache()
    # 3) CLIP 특징 (main 방식) — 칸 수 기준
    from ai.features.moment_detr_features import build_feature
    for r in new:
        d = IDX / r["youtube_id"]
        if not (d / "clip.pt").exists():
            build_feature(video_path=r["video_path"], video_id=r["youtube_id"], output_dir=str(d), overwrite=True)
            (d / f"{r['youtube_id']}_clip_features.pt").rename(d / "clip.pt")
    # 4) 프레임 + LoRA 화면 특징 (칸 수는 CLIP과 맞춤, 평가와 같음)
    import speed_opt
    from lora import load_lora
    emb = None
    for r in new:
        d = IDX / r["youtube_id"]
        if (d / "lora_640.pt").exists() and (d / "frames.npy").exists():
            continue
        if emb is None:
            emb = speed_opt.Embedder(); load_lora(emb.m, LORA / "adapter.pt")
        n = len(torch.load(d / "clip.pt")); t0 = time.time()
        frames = speed_opt.decode(Path(r["video_path"]), n, "cpu")
        np.save(d / "frames.npy", frames)
        e, _, _ = emb(frames, "torchvision", "cuda", 16)
        torch.save(e.half().cpu(), d / "lora_640.pt")
        print("특징", r["youtube_id"], n, f"{(time.time() - t0) / (r['duration_sec'] / 60):.2f}초/영상 1분", flush=True)
    cat = [{k: v for k, v in r.items() if k != "video_path"} | {"bins": len(torch.load(IDX / r["youtube_id"] / "clip.pt"))} for r in items]
    CATALOG.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {CATALOG} ({len(cat)}개)")


if __name__ == "__main__":
    main()
