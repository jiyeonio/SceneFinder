"""평가 질의 라벨링 도구 서버. 로컬 영상을 브라우저로 재생하며 질의와 정답 구간을 JSON으로 저장합니다.

    python tools/labeler/server.py --labels labels.json --videos data/raw/korean_test [다른 영상 폴더 ...] \
        [--youtube-list docs/experiments/eval_youtube_videos.tsv] [--youtube 영상ID ...]
    → http://127.0.0.1:8765 접속 (원격 서버라면 VS Code 포트 포워딩이나 ssh -L 8765:127.0.0.1:8765)

- 표준 라이브러리만 사용합니다. 영상 탐색(seek)이 되도록 HTTP Range 요청을 지원합니다.
- 저장 형식은 README.md 참고. 저장할 때마다 이전 파일을 <labels>.bak으로 남깁니다.
- 목록에 있는 영상 파일만 내려주고, 다른 경로는 열지 않습니다.
- YouTube 영상은 브라우저에서 YouTube 임베드로 재생합니다(서버는 영상을 받지 않음). --videos 폴더에
  <영상ID>.mp4가 있으면 같은 항목에서 로컬 파일 재생으로도 바꿀 수 있습니다.
"""
import argparse
import csv
import json
import mimetypes
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FORMAT = "scenefinder-labels/1"
VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".m4v"}
YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
EVAL_VIDEO_DIR = Path.home() / "scenefinder_eval/videos"
CHUNK = 1 << 20


def repo_path(path: Path) -> str:
    """저장소 안이면 루트 기준 상대 경로, 밖이면 절대 경로. data/ 같은 심볼릭 링크를 따라가지 않도록 resolve하지 않음."""
    absolute = os.path.abspath(path)
    rel = os.path.relpath(absolute, ROOT)
    return absolute if rel.startswith("..") else rel


def read_youtube_list(path):
    """TSV(머리행에 youtube_id, 선택: key·title·domain) 또는 한 줄에 ID 하나. #으로 시작하는 줄은 무시."""
    lines = [l for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if lines and "youtube_id" in lines[0].split("\t"):
        return list(csv.DictReader(lines, delimiter="\t"))
    return [{"youtube_id": l.split()[0]} for l in lines]


def scan_videos(dirs, youtube=()):
    """로컬 영상 파일과 YouTube 항목 목록. <ID>.mp4 같은 로컬 파일은 해당 YouTube 항목에 붙임."""
    files = []
    for d in dirs:
        d = Path(d)
        if not d.is_dir():
            sys.exit(f"영상 폴더가 없습니다: {d}")
        files += sorted(p for p in d.rglob("*") if p.suffix.lower() in VIDEO_EXT and p.is_file())
    by_stem = {p.stem: p for p in files}
    items, used = [], set()
    for y in youtube:
        yid = (y.get("youtube_id") or "").strip()
        if not YOUTUBE_ID.fullmatch(yid):
            sys.exit(f"YouTube ID 형식이 아닙니다: {yid!r}")
        if any(it["youtube_id"] == yid for it in items):
            continue
        local = by_stem.get(yid)
        if local:
            used.add(local)
        items.append({"youtube_id": yid, "title": y.get("title") or "", "key": y.get("key") or "",
                      "domain": y.get("domain") or "", "path": local})
    items += [{"youtube_id": None, "path": p} for p in files if p not in used]
    for i, it in enumerate(items):
        it["id"] = i
        it["file"] = repo_path(it["path"]) if it["path"] else None
        it["basename"] = it["path"].name if it["path"] else None
    return items


def validate(data):
    """저장 전 형식 확인. 문제가 있으면 메시지 목록."""
    errors = []
    if data.get("format") != FORMAT:
        errors.append(f"format은 {FORMAT}이어야 합니다")
    videos = data.get("videos", {})
    nums = {n.get("num") for n in data.get("negative_queries", [])}   # 정답 없음 질의와도 번호가 겹치면 안 됨
    for key, v in videos.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            errors.append(f"영상 키 {key!r}: 영문·숫자·_·-만 사용")
        if not v.get("file") and not v.get("youtube_id"):
            errors.append(f"영상 {key}: file 또는 youtube_id가 필요함")
        if v.get("youtube_id") and not YOUTUBE_ID.fullmatch(str(v["youtube_id"])):
            errors.append(f"영상 {key}: YouTube ID 형식이 아님")
    for q in data.get("queries", []):
        num = q.get("num")
        if num in nums:
            errors.append(f"질의 번호 중복: {num}")
        nums.add(num)
        if q.get("video") not in videos:
            errors.append(f"#{num}: videos에 없는 영상 {q.get('video')!r}")
        if q.get("type") not in ("S", "V"):
            errors.append(f"#{num}: 유형은 S 또는 V")
        if not str(q.get("query", "")).strip():
            errors.append(f"#{num}: 질의가 비어 있음")
        if q.get("source", "human") not in ("ai_draft", "human_reviewed", "human"):
            errors.append(f"#{num}: source는 ai_draft/human_reviewed/human 중 하나")
        if q.get("overlay_text") not in (None, True, False):
            errors.append(f"#{num}: overlay_text는 true/false")
        gt = q.get("gt")
        is_seg = lambda g: (isinstance(g, list) and len(g) == 2  # noqa: E731
                            and all(isinstance(x, (int, float)) for x in g) and g[1] > g[0])
        if not isinstance(gt, list) or not gt or not all(is_seg(g) for g in gt):
            errors.append(f"#{num}: 정답 구간이 없거나 끝 ≤ 시작")
    return errors


def make_handler(videos, labels_path: Path):
    by_id = {v["id"]: v for v in videos if v["path"]}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # 영상 Range 요청 로그가 너무 많아 오류만 출력
            if not str(args[1] if len(args) > 1 else "").startswith(("2", "3")):
                super().log_message(fmt, *args)

        def send_json(self, obj, status=HTTPStatus.OK):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                body = (HERE / "index.html").read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/videos":
                self.send_json([{k: v.get(k) for k in ("id", "file", "basename", "youtube_id", "title", "key", "domain")}
                                for v in videos])
            elif url.path == "/api/labels":
                if labels_path.exists():
                    self.send_json(json.loads(labels_path.read_text(encoding="utf-8")))
                else:
                    self.send_json({"format": FORMAT, "videos": {}, "queries": []})
            elif url.path == "/media":
                try:
                    video = by_id[int(parse_qs(url.query)["id"][0])]
                except (KeyError, ValueError, IndexError):
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.send_media(video["path"])
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def send_media(self, path: Path):
            size = path.stat().st_size
            start, end = 0, size - 1
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
                else:  # bytes=-N: 마지막 N바이트
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                self.send_response(HTTPStatus.PARTIAL_CONTENT)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            else:
                self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            try:
                with path.open("rb") as f:
                    f.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = f.read(min(CHUNK, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass  # 브라우저가 탐색하면서 이전 요청을 끊는 것은 정상

        def do_PUT(self):
            if urlparse(self.path).path != "/api/labels":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self.send_json({"errors": ["JSON을 읽을 수 없습니다"]}, HTTPStatus.BAD_REQUEST)
                return
            errors = validate(data)
            if errors:
                self.send_json({"errors": errors}, HTTPStatus.BAD_REQUEST)
                return
            labels_path.parent.mkdir(parents=True, exist_ok=True)
            if labels_path.exists():
                labels_path.replace(labels_path.with_name(labels_path.name + ".bak"))
            tmp = labels_path.with_name(labels_path.name + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            tmp.replace(labels_path)
            self.send_json({"ok": True, "queries": len(data["queries"])})

    return Handler


def main():
    parser = argparse.ArgumentParser(description="평가 질의 라벨링 도구")
    parser.add_argument("--labels", required=True, help="읽고 저장할 라벨 JSON (없으면 새로 만듦)")
    parser.add_argument("--videos", nargs="+", default=None,
                        help=f"영상 폴더 (여러 개 가능, 기본: data/raw/korean_test와 {EVAL_VIDEO_DIR} 중 있는 것)")
    parser.add_argument("--youtube-list", help="YouTube 영상 목록 TSV (예: docs/experiments/eval_youtube_videos.tsv)")
    parser.add_argument("--youtube", nargs="+", default=[], help="YouTube 영상 ID (여러 개 가능)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    dirs = args.videos or [d for d in (ROOT / "data/raw/korean_test", EVAL_VIDEO_DIR) if d.is_dir()]
    youtube = (read_youtube_list(args.youtube_list) if args.youtube_list else []) + [{"youtube_id": y} for y in args.youtube]
    videos = scan_videos(dirs, youtube)
    labels_path = Path(args.labels).absolute()
    n_yt = sum(1 for v in videos if v["youtube_id"])
    n_local = sum(1 for v in videos if v["path"])
    print(f"영상 {len(videos)}개 (YouTube {n_yt}개, 로컬 파일 {n_local}개), 라벨 파일: {labels_path}")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(videos, labels_path))
    print(f"http://{args.host}:{args.port} 에서 실행 중 (Ctrl+C로 종료)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
