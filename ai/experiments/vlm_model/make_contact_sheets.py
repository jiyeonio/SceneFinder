"""AI 질의 초안용 자료: 영상마다 3초 간격 프레임 16장(4×4, 48초)을 시각과 함께 한 장으로 묶은 시트와
시각이 붙은 자막 텍스트를 만든다.

    python ai/experiments/vlm_model/make_contact_sheets.py --videos /nfs/team/data/scenefinder_vlm/eval_videos \
        --subtitles /nfs/team/data/scenefinder_vlm/eval_subtitles --out /nfs/team/data/scenefinder_vlm/eval_sheets
"""
import argparse, csv, json, subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

STEP, COLS, ROWS, TW, TH = 3.0, 4, 4, 480, 270


def frames(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf",
                          f"fps=1/{STEP},scale={TW}:{TH}:force_original_aspect_ratio=decrease,pad={TW}:{TH}:(ow-iw)/2:(oh-ih)/2",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    n = len(raw) // (TW * TH * 3)
    return [Image.fromarray(np.frombuffer(raw, np.uint8, TW * TH * 3, i * TW * TH * 3).reshape(TH, TW, 3)) for i in range(n)]


def mmss(t):
    return f"{int(t) // 60}:{t % 60:04.1f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="docs/experiments/vlm_eval_split.tsv")
    ap.add_argument("--videos", required=True); ap.add_argument("--subtitles", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--font", required=True)
    a = ap.parse_args()
    font = ImageFont.truetype(a.font, 22)
    for r in csv.DictReader(open(a.split), delimiter="\t"):
        key, vid = r["key"], r["youtube_id"]
        d = Path(a.out) / key; d.mkdir(parents=True, exist_ok=True)
        fr = frames(Path(a.videos) / f"{vid}.mp4")
        per = COLS * ROWS
        for s in range(0, len(fr), per):
            sheet = Image.new("RGB", (TW * COLS, TH * ROWS), "black"); dr = ImageDraw.Draw(sheet)
            for j, im in enumerate(fr[s:s + per]):
                x, y = (j % COLS) * TW, (j // COLS) * TH
                sheet.paste(im, (x, y))
                t = (s + j) * STEP
                dr.rectangle([x, y, x + 120, y + 30], fill="black"); dr.text((x + 6, y + 2), f"{mmss(t)}", font=font, fill="yellow")
            sheet.save(d / f"sheet_{s // per:03d}_{mmss(s * STEP).replace(':', 'm')}s.jpg", quality=85)
        sub = json.loads((Path(a.subtitles) / f"{vid}.json").read_text())
        lines = [f"[{x['start_time']:.1f}–{x['end_time']:.1f}] {x['text']}" for x in sub["segments"]]
        (d / "subtitles.txt").write_text("\n".join(lines) if lines else "(자막 없음: 말이 없는 영상)", encoding="utf-8")
        (d / "info.json").write_text(json.dumps({**r, "frames_every_sec": STEP, "n_frames": len(fr)}, ensure_ascii=False, indent=1))
        print(key, vid, f"프레임 {len(fr)}, 시트 {(len(fr) + per - 1) // per}", flush=True)


if __name__ == "__main__":
    main()
