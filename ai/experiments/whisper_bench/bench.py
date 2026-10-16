"""서비스 자막 생성(Whisper) 모델별 처리 시간·GPU 메모리 측정.

    python ai/experiments/whisper_bench/bench.py --models small,large-v3-turbo --out 결과.json 영상.mp4 [영상.mp4 ...]

- 서비스와 같은 함수(backend/services/subtitles.py의 _transcribe, 같은 beam·VAD 설정)를 그대로 씁니다.
- 모델마다 새 프로세스에서 측정합니다(모델 로딩 시간·GPU 메모리를 따로 재기 위해). 첫 영상 전에 짧은 구간으로 워밍업합니다.
- 서비스처럼 torch를 먼저 불러온 상태에서 잽니다(아래 worker 주석). 결과의 device로 GPU/CPU를 확인하세요.
- GPU 메모리는 nvidia-smi의 GPU 전체 사용량을 0.2초마다 읽어, 시작 전 기준값 대비 최대 증가량을 기록합니다.
  컨테이너에서는 프로세스별 사용량이 안 보여서 이렇게 재므로, **다른 GPU 작업이 없을 때 돌려야** 맞는 값이 나옵니다.
- 결과(영상별 길이·처리 시간·실시간 대비 배속·문장 수, 모델 로딩 시간, 최대 GPU 메모리)를 --out JSON에 저장합니다.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def gpu_used_mib():
    """GPU 전체 사용량. 컨테이너에서는 nvidia-smi가 프로세스별 사용량을 못 보여줘서, 다른 작업이 없을 때
    기준값 대비 증가량으로 잽니다."""
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.split()[0])


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


def worker(model, videos, out_path):
    """한 모델을 이 프로세스에서 측정."""
    os.environ["WHISPER_MODEL_SIZE"] = model
    sys.path.insert(0, str(ROOT / "backend"))
    # 서비스는 시작할 때 MiniLM(torch)을 먼저 올리므로 torch가 CUDA 라이브러리(libcublas)를 불러온 상태에서 Whisper가 돕니다.
    # torch 없이 faster-whisper만 불러오면 Linux에서 libcublas.so.12를 못 찾아 CPU로 넘어가므로 서비스와 같게 먼저 불러옴.
    import torch  # noqa: F401
    from services import subtitles as st

    base = gpu_used_mib()
    peak, stop = [0], threading.Event()

    def watch():
        while not stop.is_set():
            peak[0] = max(peak[0], gpu_used_mib() - base)
            time.sleep(0.2)
    threading.Thread(target=watch, daemon=True).start()

    t = time.perf_counter()
    st._get_model("cuda")
    load_sec = time.perf_counter() - t
    after_load = gpu_used_mib() - base

    # 워밍업: 첫 영상 앞 20초
    with tempfile.TemporaryDirectory() as tmp:
        clip = Path(tmp) / "warm.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(videos[0]), "-t", "20", "-c", "copy", str(clip)], check=True)
        st._transcribe(str(clip))

    results = []
    for v in videos:
        dur = duration(v)
        t = time.perf_counter()
        items, lang, _ = st._transcribe(str(v))
        sec = time.perf_counter() - t
        results.append({"video": Path(v).stem, "duration_sec": round(dur, 1), "transcribe_sec": round(sec, 2),
                        "x_realtime": round(dur / sec, 1), "segments": len(items), "language": lang,
                        "device": st._model_device})
        print(f"  {model} {Path(v).stem}: {dur:.0f}초 영상 → {sec:.1f}초 ({dur / sec:.0f}배속), 문장 {len(items)}개", flush=True)
    stop.set()
    Path(out_path).write_text(json.dumps({"model": model, "load_sec": round(load_sec, 2), "gpu_mib_base": base,
                                          "gpu_mib_after_load": after_load, "gpu_mib_peak": peak[0], "videos": results},
                                         ensure_ascii=False, indent=1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+")
    parser.add_argument("--models", default="small,large-v3-turbo")
    parser.add_argument("--out", help="결과 JSON (측정을 시작할 때 필수)")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", help=argparse.SUPPRESS)
    args = parser.parse_args()
    videos = [Path(v).resolve() for v in args.videos]
    if args.worker:
        worker(args.worker, videos, args.worker_out)
        return
    if not args.out:
        parser.error("--out이 필요합니다")
    import socket
    report = {"host": socket.gethostname(),
              "gpu": subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip(),
              "models": []}
    for m in args.models.split(","):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        print(f"== {m}", flush=True)
        subprocess.run([sys.executable, __file__, *map(str, videos), "--worker", m, "--worker-out", tmp], check=True)
        report["models"].append(json.loads(Path(tmp).read_text()))
        os.unlink(tmp)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print("저장:", args.out)


if __name__ == "__main__":
    main()
