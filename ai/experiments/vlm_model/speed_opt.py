"""Qwen3-VL-Embedding-2B 프레임 특징 추출 속도 최적화 측정 (dev 영상, 640×360).

단계별 시간(프레임 읽기 / 전처리 / 모델 계산)을 영상 1분당 초로 재고, 기준 설정(extract_eval_features.py와 같은
CPU 디코딩 + torchvision 전처리 CPU + 묶음 8, eval_features/qwen_640_v0)으로 만든 특징과의 코사인 유사도로
결과가 같은지 확인한다. 결과 정리: docs/experiments/vlm_speed_opt.md

    python ai/experiments/vlm_model/speed_opt.py --configs base,prep_gpu,dec_gpu,bs16,bs32 \
        --out ai/experiments/vlm_model/results/speed_opt.json
"""
import argparse, csv, json, subprocess, time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[3]
VIDEOS = Path("/nfs/team/data/scenefinder_vlm/eval_videos")
FEATS = Path("/nfs/team/data/scenefinder_vlm/eval_features")
W, H, CLIP_LEN = 640, 360, 2.0
INSTR = "Represent the user's input."

# 설정: (디코딩, 전처리 백엔드, 전처리 장치, 묶음 크기). 순서대로 하나씩 바꿔 가며 효과를 본다.
CONFIGS = {
    "base":     ("cpu", "torchvision", "cpu", 8),    # 지금 extract_eval_features.py와 같음
    "prep_gpu": ("cpu", "torchvision", "cuda", 8),   # 1) 전처리를 GPU로 (uint8 텐서를 GPU에 올려 넘김)
    "dec_gpu":  ("gpu", "torchvision", "cuda", 8),   # 2) + NVDEC 디코딩
    "bs16":     ("gpu", "torchvision", "cuda", 16),  # 3) + 묶음 16
    "bs32":     ("gpu", "torchvision", "cuda", 32),  #    + 묶음 32
    # GPU 디코딩이 느리고 결과도 달라져(dec_gpu) CPU 디코딩으로 되돌려 묶음 크기만 바꿈
    "cpu_bs16": ("cpu", "torchvision", "cuda", 16),
    "cpu_bs32": ("cpu", "torchvision", "cuda", 32),
    # 4) 추가: 다음 영상 디코딩(CPU)을 지금 영상 계산(GPU)과 겹침. 실제 걸린 시간(wall)으로 잼
    "overlap":  ("cpu", "torchvision", "cuda", 16, "overlap"),
}


def probe_size(path):
    w, h = map(int, subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                             "stream=width,height", "-of", "csv=p=0", str(path)]).decode().split(","))
    return w, h


def decode(path, n, how):
    """2초 칸 가운데(1, 3, 5…초) 프레임 n장, 비율 유지해 640×360 안에 넣고 검은 여백. uint8 [n, H, W, 3]."""
    if how == "cpu":
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{CLIP_LEN / 2}", "-i", str(path), "-vf",
               f"fps=1/{CLIP_LEN},scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
    else:
        # NVDEC로 디코딩·축소(scale_cuda)하고, 여백만 CPU에서 채움. 축소 크기는 CPU 경로와 같게 직접 계산
        vw, vh = probe_size(path)
        s = min(W / vw, H / vh)
        sw, sh = int(vw * s) // 2 * 2, int(vh * s) // 2 * 2
        cmd = ["ffmpeg", "-v", "error", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda", "-ss", f"{CLIP_LEN / 2}",
               "-i", str(path), "-vf", f"fps=1/{CLIP_LEN},scale_cuda={sw}:{sh},hwdownload,format=nv12,"
                                       f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"]
    raw = subprocess.run(cmd + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    m = len(raw) // (W * H * 3)
    arr = np.frombuffer(raw, np.uint8)[: m * W * H * 3].reshape(m, H, W, 3)
    if m < n:
        arr = np.concatenate([arr, np.repeat(arr[-1:], n - m, 0)])
    return arr[:n]


class Embedder:
    def __init__(self):
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        rid = "Qwen/Qwen3-VL-Embedding-2B"
        self.m = Qwen3VLForConditionalGeneration.from_pretrained(rid, dtype=torch.bfloat16).model.cuda().eval()
        # 기본 백엔드가 이미 torchvision(빠른 전처리). PIL 백엔드는 이 버전에서 영상 프로세서 때문에 불러올 수 없어 비교에서 뺌
        self.proc = {"torchvision": AutoProcessor.from_pretrained(rid, padding_side="right")}

    @torch.no_grad()
    def __call__(self, frames, backend, device, bs):
        """frames uint8 [n,H,W,3] → (임베딩 [n,2048], 전처리 초, 모델 계산 초)"""
        p = self.proc[backend]
        msgs = [{"role": "system", "content": [{"type": "text", "text": INSTR}]},
                {"role": "user", "content": [{"type": "image"}]}]
        text = p.apply_chat_template([msgs], add_generation_prompt=True, tokenize=False)[0]
        outs, t_prep, t_fwd = [], 0.0, 0.0
        for i in range(0, len(frames), bs):
            torch.cuda.synchronize(); t0 = time.time()
            chunk = frames[i:i + bs]
            if backend == "pil":
                from PIL import Image
                imgs = [Image.fromarray(f) for f in chunk]
                x = p(text=[text] * len(imgs), images=imgs, padding=True, return_tensors="pt")
            else:
                t = torch.from_numpy(np.ascontiguousarray(chunk)).permute(0, 3, 1, 2)
                if device == "cuda":
                    t = t.cuda(non_blocking=True)
                x = p(text=[text] * len(t), images=list(t), padding=True, return_tensors="pt",
                      **({"device": "cuda"} if device == "cuda" else {}))
            x = x.to("cuda")
            torch.cuda.synchronize(); t1 = time.time()
            h = self.m(**x).last_hidden_state
            last = x["attention_mask"].sum(1) - 1
            outs.append(F.normalize(h[torch.arange(h.shape[0], device=h.device), last].float(), dim=-1))
            torch.cuda.synchronize(); t2 = time.time()
            t_prep += t1 - t0; t_fwd += t2 - t1
        return torch.cat(outs), t_prep, t_fwd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(ROOT / "docs/experiments/vlm_eval_split.tsv"), delimiter="\t") if r["split"] == "dev"]
    emb = Embedder()
    # 예열 (첫 호출의 CUDA 초기화 시간 제외)
    emb(decode(VIDEOS / f"{rows[0]['youtube_id']}.mp4", 16, "cpu"), "torchvision", "cpu", 8)
    out = json.loads(Path(a.out).read_text()) if Path(a.out).exists() else {}
    for name in a.configs.split(","):
        dec, backend, device, bs = CONFIGS[name][:4]
        overlap = len(CONFIGS[name]) > 4
        tot = {"decode": 0.0, "prep": 0.0, "fwd": 0.0, "video_sec": 0.0, "frames": 0}
        cos_all = []
        torch.cuda.reset_peak_memory_stats()
        refs = {r["youtube_id"]: torch.load(FEATS / "qwen_640_v0" / f"{r['youtube_id']}.pt").float().cuda() for r in rows}

        def dec_timed(vid):
            t0 = time.time(); f = decode(VIDEOS / f"{vid}.mp4", len(refs[vid]), dec); return f, time.time() - t0

        from concurrent.futures import ThreadPoolExecutor
        pool = ThreadPoolExecutor(1)
        wall0 = time.time()
        nxt = pool.submit(dec_timed, rows[0]["youtube_id"]) if overlap else None
        for i, r in enumerate(rows):
            vid = r["youtube_id"]; ref = refs[vid]
            if overlap:
                frames, t_dec = nxt.result()
                if i + 1 < len(rows):
                    nxt = pool.submit(dec_timed, rows[i + 1]["youtube_id"])
            else:
                frames, t_dec = dec_timed(vid)
            e, t_prep, t_fwd = emb(frames, backend, device, bs)
            cos_all.append((e * F.normalize(ref, dim=-1)).sum(-1).cpu())
            tot["decode"] += t_dec; tot["prep"] += t_prep; tot["fwd"] += t_fwd
            tot["video_sec"] += float(r["duration_sec"]); tot["frames"] += len(ref)
        wall = time.time() - wall0
        cos = torch.cat(cos_all)
        per_min = {k: round(tot[k] / tot["video_sec"] * 60, 3) for k in ("decode", "prep", "fwd")}
        res = {"config": dict(zip(("decode", "preprocess_backend", "preprocess_device", "batch"), (dec, backend, device, bs)),
                              overlap=overlap),
               "sec_per_video_min": {**per_min, "total": round(sum(per_min.values()), 3),
                                     "wall": round(wall / tot["video_sec"] * 60, 3)},
               "cos_vs_base": {"mean": round(float(cos.mean()), 5), "min": round(float(cos.min()), 5)},
               "peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2), "frames": tot["frames"]}
        out[name] = res
        print(name, json.dumps(res, ensure_ascii=False), flush=True)
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
