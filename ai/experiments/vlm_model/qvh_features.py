"""QVHighlights 영상의 Qwen3-VL-Embedding-2B 프레임 특징 (구간 검색 모델 VLM 버전의 영상 입력).

- 2초 칸마다 가운데 프레임(1, 3, 5…초) 1장, 640×360, CPU 디코딩 + GPU 전처리 + 묶음 16
  (평가 영상 특징과 같은 설정, docs/experiments/vlm_speed_opt.md). 다음 영상 디코딩을 지금 영상 계산과 겹친다.
- 출력: <out>/<vid>.npz, 키 "features" [칸 수, 2048] float16 (Moment-DETR 데이터 로더 형식). 칸 수는 ceil(길이/2), 최대 75.
- 이미 있는 파일은 건너뛰므로 끊겨도 다시 실행하면 이어진다. 진행 로그와 시간은 <out>/progress.log, timing.json.

    python ai/experiments/vlm_model/qvh_features.py --videos /nfs/team/data/scenefinder_vlm/qvh/videos/videos \
        --out /nfs/team/data/scenefinder_vlm/qvh/features/qwen3vl_emb2b_640
"""
import argparse, json, math, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
import speed_opt  # noqa: E402

CLIP_LEN, MAX_V_L, BATCH = 2.0, 75, 16


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else None


def load(path):
    t0 = time.time()
    dur = duration(path)
    if not dur:
        return None, None, time.time() - t0
    n = min(MAX_V_L, math.ceil(dur / CLIP_LEN))
    try:
        frames = speed_opt.decode(path, n, "cpu")
    except Exception:   # 깨진 영상은 건너뛰고 기록
        return None, dur, time.time() - t0
    return frames, dur, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    todo = [p for p in sorted(Path(a.videos).glob("*.mp4")) if not (out / f"{p.stem}.npz").exists()]
    if a.limit:
        todo = todo[:a.limit]
    log = open(out / "progress.log", "a")
    say = lambda m: (print(m, flush=True), log.write(m + "\n"), log.flush())  # noqa: E731
    say(f"{time.strftime('%F %T')} 시작: 남은 영상 {len(todo)}개 (이미 {len(list(out.glob('*.npz')))}개 있음)")
    if not todo:
        return
    emb = speed_opt.Embedder()
    pool = ThreadPoolExecutor(1)
    nxt = pool.submit(load, todo[0])
    t_start = time.time(); tot = {"video_sec": 0.0, "wall": 0.0, "n": 0, "failed": []}
    for i, p in enumerate(todo):
        frames, dur, _ = nxt.result()
        if i + 1 < len(todo):
            nxt = pool.submit(load, todo[i + 1])
        if frames is None:
            tot["failed"].append(p.name); say(f"실패(읽기): {p.name}"); continue
        e, _, _ = emb(frames, "torchvision", "cuda", BATCH)
        np.savez(out / f"{p.stem}.npz", features=e.cpu().numpy().astype(np.float16))
        tot["video_sec"] += dur; tot["n"] += 1
        if (i + 1) % 200 == 0 or i + 1 == len(todo):
            wall = time.time() - t_start
            say(f"{time.strftime('%F %T')} {i + 1}/{len(todo)}  영상 1분당 {wall / tot['video_sec'] * 60:.2f}초  "
                f"남은 시간 약 {wall / (i + 1) * (len(todo) - i - 1) / 3600:.1f}시간  GPU 최대 {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")
    tot["wall"] = time.time() - t_start
    (out / "timing.json").write_text(json.dumps({**tot, "sec_per_video_min": tot["wall"] / max(tot["video_sec"], 1) * 60},
                                                ensure_ascii=False, indent=1))
    say(f"{time.strftime('%F %T')} 끝: {tot['n']}개, 실패 {len(tot['failed'])}개")


if __name__ == "__main__":
    main()
