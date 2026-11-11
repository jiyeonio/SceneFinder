"""평가 영상(vlm_eval_split.tsv)을 받는다. 서버 IP가 봇 차단된 적이 있어 영상 사이 40초 이상 쉬고,
403·로그인 요구가 나오면 바로 멈춘다. 이미 받은 영상은 건너뛴다.

720p까지 받는다(서비스는 480p). 화면 글자 인식은 해상도 영향을 dev에서 비교해야 하고, 720p 파일을 줄이면
480p 조건도 재현할 수 있다.

    PATH=$HOME/.local/node/node-v22.12.0-linux-x64/bin:$PATH \
    python ai/experiments/vlm_model/download_eval_videos.py --out /nfs/team/data/scenefinder_vlm/eval_videos
"""
import argparse, csv, sys, time
from pathlib import Path

import yt_dlp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="docs/experiments/vlm_eval_split.tsv")
    ap.add_argument("--out", required=True)
    ap.add_argument("--gap", type=float, default=40)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ids = [r["youtube_id"] for r in csv.DictReader(open(a.split), delimiter="\t")]
    opts = {
        "format": "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/b[height<=720][vcodec^=avc1]/bv*[height<=720]+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": f"{out}/%(id)s.%(ext)s",
        "js_runtimes": {"node": {}},
        "quiet": True, "no_warnings": True, "noprogress": True,
    }
    first = True
    for vid in ids:
        if (out / f"{vid}.mp4").exists():
            print(f"{vid} 있음, 건너뜀", flush=True); continue
        if not first:
            time.sleep(a.gap)
        first = False
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
            print(f"{vid} 받음 {info.get('height')}p {info.get('duration')}초", flush=True)
        except Exception as e:
            msg = str(e)
            print(f"{vid} 실패: {msg[:200]}", flush=True)
            if "403" in msg or "Sign in" in msg or "confirm you" in msg:
                print("403/로그인 요구 → 중단", flush=True); sys.exit(2)


if __name__ == "__main__":
    main()
