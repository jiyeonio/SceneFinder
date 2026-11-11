"""평가 영상 자막 만들기: YouTube 업로더 수동 한국어 자막이 있으면 그것, 없으면 Whisper large-v3-turbo.

- 수동 자막 여부는 YouTube Data API captions.list의 trackKind(standard = 업로더, asr = 자동 생성)로 판단한다.
  자동 생성(asr) 자막은 쓰지 않는다.
- Whisper는 서비스 코드(backend/services/subtitles.py)의 _transcribe를 그대로 불러 같은 설정
  (large-v3-turbo, beam 5, VAD, 말이 거의 없으면 자막 없음)으로 만든다.
- 출력은 서비스와 같은 형식({"language", "language_probability", "segments": [{start_time, end_time, text}]})에
  "source"를 더해 --out 폴더에 {유튜브ID}.json으로 저장하고, split 표에 subtitle_source 열을 채운다.

    python ai/experiments/vlm_model/make_eval_subtitles.py \
        --videos /nfs/team/data/scenefinder_vlm/eval_videos --out /nfs/team/data/scenefinder_vlm/eval_subtitles
"""
import argparse, csv, json, os, re, sys, time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "services"))
os.environ.setdefault("WHISPER_MODEL_SIZE", "large-v3-turbo")

SRC_MANUAL = "youtube_manual_ko"
SRC_WHISPER = "whisper_large-v3-turbo"


def manual_ko_track(vid, key):
    j = requests.get("https://www.googleapis.com/youtube/v3/captions",
                     params={"part": "snippet", "videoId": vid, "key": key}, timeout=30).json()
    if "items" not in j:
        raise RuntimeError(f"{vid}: captions.list 실패 {j.get('error', {}).get('message', '')[:100]}")
    return any(i["snippet"]["trackKind"] == "standard" and i["snippet"]["language"].startswith("ko") for i in j["items"])


def vtt_segments(path):
    ts = lambda t: sum(float(x) * 60 ** i for i, x in enumerate(reversed(t.replace(",", ".").split(":"))))  # noqa: E731
    segs, cur = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"([\d:.,]+)\s+-->\s+([\d:.,]+)", line)
        if m:
            cur = {"start_time": round(ts(m[1]), 2), "end_time": round(ts(m[2]), 2), "text": ""}
            segs.append(cur)
        elif cur is not None and line.strip():
            cur["text"] = (cur["text"] + " " + re.sub(r"<[^>]+>", "", line).strip()).strip()
        else:
            cur = None
    return [s for s in segs if s["text"]]


def download_manual(vid, out_dir):
    import yt_dlp
    opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": False, "subtitleslangs": ["ko"],
            "subtitlesformat": "vtt", "outtmpl": f"{out_dir}/%(id)s.%(ext)s", "js_runtimes": {"node": {}},
            "source_address": "0.0.0.0", "quiet": True}
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([f"https://www.youtube.com/watch?v={vid}"])
    return vtt_segments(next(Path(out_dir).glob(f"{vid}*.vtt")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="docs/experiments/vlm_eval_split.tsv")
    ap.add_argument("--videos", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    load_dotenv(ROOT / "backend" / ".env")
    key = os.getenv("YOUTUBE_API_KEY") or sys.exit("YOUTUBE_API_KEY 없음")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(a.split), delimiter="\t"))
    fields = list(rows[0]) + ([] if "subtitle_source" in rows[0] else ["subtitle_source"])

    from subtitles import _transcribe, MIN_SUBTITLE_SEGMENTS, MIN_SUBTITLE_CHARS, WHISPER_MODEL_SIZE
    assert WHISPER_MODEL_SIZE == "large-v3-turbo", WHISPER_MODEL_SIZE
    fetched_youtube = False
    for r in rows:
        vid = r["youtube_id"]; t0 = time.time()
        if manual_ko_track(vid, key):
            if fetched_youtube:
                time.sleep(40)  # 영상 다운로드와 같은 간격 규칙
            items, lang, prob, src = download_manual(vid, out), "ko", 1.0, SRC_MANUAL
            fetched_youtube = True
        else:
            items, lang, prob = _transcribe(str(Path(a.videos) / f"{vid}.mp4"))
            if len(items) < MIN_SUBTITLE_SEGMENTS or sum(len(i["text"]) for i in items) < MIN_SUBTITLE_CHARS:
                items = []
            src = SRC_WHISPER
        (out / f"{vid}.json").write_text(json.dumps(
            {"source": src, "language": lang, "language_probability": round(prob, 4), "segments": items},
            ensure_ascii=False, indent=2), encoding="utf-8")
        r["subtitle_source"] = src
        print(f"{r['key']} {vid} {src} 문장 {len(items)} 언어 {lang} ({time.time() - t0:.1f}초)", flush=True)

    with open(a.split, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t"); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
