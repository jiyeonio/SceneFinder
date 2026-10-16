"""VLM으로 2초마다 한국어 장면 설명문을 만듭니다. (방식 (e)용)

    python ai/experiments/translation_compare/captions.py --out /tmp/translation_compare [--variants qwen_excl,varco_excl,qwen_incl] [--queries 라벨링.json]

- 프레임: 각 2초 구간의 가운데 시점 1장 (CLIP feature와 같은 간격). 긴 변 640px로 축소
- 생성: greedy(무작위 없음), 최대 80토큰
- 시간: 1장씩 처리(batch 1)한 설명문을 결과로 쓰고, 같은 프레임을 묶음 처리(batch 8)한 시간도 따로 측정
- 결과: --out/captions_<variant>.json (저장소에는 쓰지 않음). 실행한 질의 세트의 영상만 들어가고 기존 파일은 덮어씀
- 영상: --queries를 주면 그 JSON에서 질의가 있는 영상, 없으면 queries.py의 영상
"""
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import query_set  # noqa: E402
from run import duration  # noqa: E402

CLIP_LEN = 2.0
MAX_SIDE = 640
MAX_NEW_TOKENS = 80
BATCH_SIZE = 8

PROMPT_EXCLUDE_TEXT = (
    "이 영상 장면을 보고 한국어 한 문장으로 설명하세요. 보이는 사람, 사물, 동작, 장소를 구체적으로 쓰세요. "
    "화면에 덧씌운 자막이나 글자는 읽지 말고 무시하세요. 설명 문장만 출력하세요."
)
PROMPT_INCLUDE_TEXT = (
    "이 영상 장면을 보고 한국어 한 문장으로 설명하세요. 보이는 사람, 사물, 동작, 장소를 구체적으로 쓰고, "
    "화면에 글자나 자막이 있으면 그 내용도 함께 쓰세요. 설명 문장만 출력하세요."
)

VARIANTS = {
    "qwen_excl": ("Qwen/Qwen3-VL-4B-Instruct", PROMPT_EXCLUDE_TEXT),
    "varco_excl": ("NCSOFT/VARCO-VISION-2.0-1.7B", PROMPT_EXCLUDE_TEXT),
    "qwen_incl": ("Qwen/Qwen3-VL-4B-Instruct", PROMPT_INCLUDE_TEXT),
}
MODEL_INFO = {
    "Qwen/Qwen3-VL-4B-Instruct": {"license": "Apache-2.0", "dtype": torch.bfloat16},
    "NCSOFT/VARCO-VISION-2.0-1.7B": {"license": "CC-BY-NC-4.0 (비상업적 이용만 허용)", "dtype": torch.float16},
}


def extract_frames(path: Path, dur: float):
    """2초 구간마다 가운데 프레임 1장. (시작, 끝, PIL 이미지) 목록."""
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(math.ceil(dur / CLIP_LEN)):
            start, end = k * CLIP_LEN, min((k + 1) * CLIP_LEN, dur)
            # 마지막 구간이 아주 짧으면 가운데 시점이 마지막 프레임 뒤일 수 있어 끝 직전으로 당김
            t = min((start + end) / 2, max(0.0, dur - 0.1))
            f = Path(tmp) / f"{k:05d}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                            "-vf", f"scale='if(gt(iw,ih),{MAX_SIDE},-2)':'if(gt(iw,ih),-2,{MAX_SIDE})'", str(f)], check=True)
            if not f.exists():   # 그래도 프레임이 없으면(영상 끝) 이 구간은 건너뜀
                continue
            frames.append((start, end, Image.open(f).convert("RGB")))
    return frames


def load_model(name):
    from transformers import AutoProcessor
    dtype = MODEL_INFO[name]["dtype"]
    if "Qwen3-VL" in name:
        from transformers import Qwen3VLForConditionalGeneration as Cls
    else:
        from transformers import LlavaOnevisionForConditionalGeneration as Cls
    model = Cls.from_pretrained(name, dtype=dtype, attn_implementation="sdpa").to("cuda").eval()
    processor = AutoProcessor.from_pretrained(name)
    processor.tokenizer.padding_side = "left"   # 묶음 생성 시 왼쪽 패딩
    return model, processor, dtype


@torch.no_grad()
def caption_batch(model, processor, dtype, images, prompt):
    convs = [[{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}] for _ in images]
    texts = [processor.apply_chat_template(c, add_generation_prompt=True, tokenize=False) for c in convs]
    inputs = processor(text=texts, images=images, padding=True, return_tensors="pt").to("cuda")
    if "pixel_values" in inputs:
        inputs["pixel_values"] = inputs["pixel_values"].to(dtype)
    out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
    trimmed = out[:, inputs["input_ids"].shape[1]:]
    return [t.strip() for t in processor.batch_decode(trimmed, skip_special_tokens=True)], int(trimmed.numel())


def timed(fn, *a):
    torch.cuda.synchronize(); t = time.perf_counter(); r = fn(*a); torch.cuda.synchronize()
    return r, time.perf_counter() - t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "translation_compare"))
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--skip-batch-timing", action="store_true", help="묶음 처리 시간 측정 생략")
    parser.add_argument("--queries", default=None, help="라벨링 도구가 저장한 질의 JSON (없으면 queries.py)")
    parser.add_argument("--subset", choices=query_set.SUBSETS, default=None,
                        help="dev/test 영상의 질의만 (설정은 dev에서만 정하고 test는 최종 보고에만)")
    args = parser.parse_args()
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=True)

    qs = query_set.load(args.queries, args.subset)
    videos = {k: qs.video_path(k) for k in qs.video_keys}
    t0 = time.perf_counter()
    frames = {k: extract_frames(p, duration(p)) for k, p in videos.items()}
    extract_sec = time.perf_counter() - t0
    print("프레임:", {k: len(v) for k, v in frames.items()}, f"추출 {extract_sec:.1f}초", flush=True)

    loaded = {}
    for variant in args.variants.split(","):
        name, prompt = VARIANTS[variant]
        if name not in loaded:
            loaded.clear(); torch.cuda.empty_cache()
            (loaded[name]), load_sec = timed(load_model, name)
            print(f"{name} 로딩 {load_sec:.1f}초", flush=True)
        model, processor, dtype = loaded[name]
        caption_batch(model, processor, dtype, [next(iter(frames.values()))[0][2]], prompt)   # 워밍업

        # 1장씩 처리 (결과로 사용)
        torch.cuda.reset_peak_memory_stats()
        result, single, tokens = {}, {}, 0
        for k, fr in frames.items():
            texts, secs = [], []
            for start, end, img in fr:
                (txt, n), sec = timed(caption_batch, model, processor, dtype, [img], prompt)
                texts.append({"start_time": start, "end_time": end, "text": txt[0]}); secs.append(sec); tokens += n
            result[k] = texts
            single[k] = {"frames": len(fr), "total_sec": sum(secs), "per_frame_sec": sum(secs) / len(secs)}
            print(f"  {variant} {k}: {len(fr)}장 {sum(secs):.1f}초 (장당 {sum(secs)/len(secs):.2f}초)", flush=True)
        peak_single = torch.cuda.max_memory_allocated() / 2**30

        # 묶음 처리 (시간만 측정)
        batch = None
        if not args.skip_batch_timing:
            torch.cuda.reset_peak_memory_stats()
            batch = {}
            for k, fr in frames.items():
                imgs = [img for _, _, img in fr]
                total = 0.0
                for i in range(0, len(imgs), BATCH_SIZE):
                    _, sec = timed(caption_batch, model, processor, dtype, imgs[i:i + BATCH_SIZE], prompt)
                    total += sec
                batch[k] = {"frames": len(fr), "total_sec": total, "per_frame_sec": total / len(fr)}
            batch["peak_gpu_gib"] = torch.cuda.max_memory_allocated() / 2**30
            print(f"  {variant} 묶음(batch {BATCH_SIZE}) 합계 {sum(v['total_sec'] for k, v in batch.items() if k != 'peak_gpu_gib'):.1f}초", flush=True)

        meta = {"variant": variant, "model": name, "license": MODEL_INFO[name]["license"],
                "dtype": str(MODEL_INFO[name]["dtype"]).replace("torch.", ""), "prompt": prompt,
                "frame_interval_sec": CLIP_LEN, "max_side_px": MAX_SIDE, "max_new_tokens": MAX_NEW_TOKENS,
                "batch_size": BATCH_SIZE, "frame_extract_sec": extract_sec, "generated_tokens": tokens,
                "single": single, "peak_gpu_gib_single": peak_single, "batch": batch,
                "gpu": torch.cuda.get_device_name(0), "queries_source": qs.source}
        path = out / f"captions_{variant}.json"
        path.write_text(json.dumps({"meta": meta, "videos": result}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장:", path, flush=True)


if __name__ == "__main__":
    main()
