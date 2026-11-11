"""평가 영상 특징 추출 (예비 실험·평가 공용). 한 번 뽑아 NFS에 저장하고 모든 방식이 같은 파일을 쓴다.

- clip: 서비스와 같은 Moment-DETR용 CLIP ViT-B/32 2초 특징 (ai.features.moment_detr_features.build_feature)
  → B2·B3, 그리고 다국어 CLIP 화면 검색(F-CLIP)이 같이 씀
- qwen_640 / qwen_1280: 2초 칸마다 가운데 프레임을 640×360 / 1280×720으로 줄여 Qwen3-VL-Embedding-2B 임베딩 (F-VLM)

영상별 추출 시간(프레임 읽기 포함)과 GPU 최대 메모리를 timing.json에 남긴다.

    python ai/experiments/vlm_model/extract_eval_features.py --subset dev --kinds clip,qwen_640,qwen_1280
"""
import argparse, csv, json, sys, time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
VIDEOS = Path("/nfs/team/data/scenefinder_vlm/eval_videos")
OUT = Path("/nfs/team/data/scenefinder_vlm/eval_features")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default=str(ROOT / "docs/experiments/vlm_eval_split.tsv"))
    ap.add_argument("--subset", choices=["dev", "test"], required=True)
    ap.add_argument("--kinds", default="clip,qwen_640,qwen_1280")
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.split), delimiter="\t") if r["split"] == a.subset]
    kinds = a.kinds.split(",")
    tpath = OUT / "timing.json"
    timing = json.loads(tpath.read_text()) if tpath.exists() else {}

    if "clip" in kinds:
        from ai.features.moment_detr_features import build_feature
        (OUT / "clip").mkdir(parents=True, exist_ok=True)
        for r in rows:
            torch.cuda.reset_peak_memory_stats(); t0 = time.time()
            build_feature(video_path=str(VIDEOS / f"{r['youtube_id']}.mp4"), video_id=r["youtube_id"],
                          output_dir=str(OUT / "clip"), overwrite=True)
            timing.setdefault(r["key"], {})["clip"] = {"sec": round(time.time() - t0, 2), "video_sec": float(r["duration_sec"]),
                                                       "peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
            print(r["key"], "clip", timing[r["key"]]["clip"], flush=True)

    qk = [k for k in kinds if k.startswith("qwen_")]
    if qk:
        # 속도 최적화 결과(docs/experiments/vlm_speed_opt.md) 채택 설정: CPU 디코딩 + GPU 전처리 + 묶음 16
        import speed_opt
        emb = speed_opt.Embedder()
        for k in qk:
            w = int(k.split("_")[1]); h = w * 9 // 16
            speed_opt.W, speed_opt.H = w, h
            (OUT / k).mkdir(parents=True, exist_ok=True)
            for r in rows:
                n = len(torch.load(OUT / "clip" / f"{r['youtube_id']}_clip_features.pt"))  # CLIP 칸 수와 맞춤
                torch.cuda.reset_peak_memory_stats(); t0 = time.time()
                frames = speed_opt.decode(VIDEOS / f"{r['youtube_id']}.mp4", n, "cpu")
                t1 = time.time()
                e, _, _ = emb(frames, "torchvision", "cuda", 16)
                torch.save(e.half().cpu(), OUT / k / f"{r['youtube_id']}.pt")
                timing.setdefault(r["key"], {})[k] = {"sec": round(time.time() - t0, 2), "decode_sec": round(t1 - t0, 2),
                                                      "video_sec": float(r["duration_sec"]), "n": n,
                                                      "peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
                print(r["key"], k, timing[r["key"]][k], flush=True)
    tpath.write_text(json.dumps(timing, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
