from pathlib import Path
import yt_dlp

# YouTube 서명 확인용 JS 런타임. PATH에 있는 node를 쓰고, 설치돼 있으면 deno도 사용합니다.
# (런타임이 없으면 "No supported JavaScript runtime" 경고와 함께 일부 형식이 막혀 403이 날 수 있음)
JS_RUNTIMES = {"node": {}, "deno": {}}


def download_video(youtube_id: str, out_dir: str = "data/raw") -> Path:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bv*[height<=480][vcodec^=avc1]+ba[ext=m4a]/b[height<=480][vcodec^=avc1]/bv*[height<=480]+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": f"{out_dir}/%(id)s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "retries": 3,
        "socket_timeout": 30,
        "js_runtimes": JS_RUNTIMES,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={youtube_id}"])
    return Path(out_dir) / f"{youtube_id}.mp4"

if __name__ == "__main__":
    import sys
    p = download_video(sys.argv[1])
    print("saved:", p, p.stat().st_size // 1024, "KB")