"""라벨 JSON ↔ ai/experiments/translation_compare/queries.py 형식 변환.

    # 라벨 JSON → queries.py 형식 (VIDEO_FILES, VIDEO_NAMES, QUERIES)
    python tools/labeler/convert.py to-py labels.json [-o 출력.py]

    # 기존 queries.py → 라벨 JSON (기존 20개 질의를 라벨링 도구에서 이어서 편집할 때)
    python tools/labeler/convert.py from-py -o labels.json

run.py·captions.py·fusion.py는 --queries labels.json으로 JSON을 직접 읽으므로, to-py는 queries.py를
새 세트로 바꾸고 싶을 때만 씁니다. TRANSLATION_QUALITY·VLM_V_ANALYSIS(작성자 판단)는 변환하지 않습니다.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = ROOT / "ai/experiments/translation_compare"
LOCAL_VIDEO_DIR = "data/raw/korean_test"
FORMAT = "scenefinder-labels/1"
sys.path.insert(0, str(EXP_DIR))


def num_str(x):
    """13.0 → 13, 13.5 → 13.5 (queries.py의 정수 표기 유지)"""
    x = float(x)
    return str(int(x)) if x.is_integer() else repr(round(x, 1))


def to_py(labels_path, out):
    import query_set

    qs = query_set.load(labels_path)   # 형식·값 확인을 같이 함
    data = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    keys = qs.video_keys
    lines = [f'"""{Path(labels_path).name}에서 변환한 평가 질의 (tools/labeler/convert.py to-py).', "",
             "유형: S = 말로 설명되는 장면, V = 말로는 안 나오고 화면에만 보이는 장면", '"""', "",
             f"# 영상 키 → ({LOCAL_VIDEO_DIR} 파일명 또는 저장소 기준 경로, 인수인계 폴더의 파일명)",
             "VIDEO_FILES = {"]
    for k in keys:
        file = qs.videos[k]["file"]
        rest = file[len(LOCAL_VIDEO_DIR) + 1:]
        local = rest if file.startswith(LOCAL_VIDEO_DIR + "/") and "/" not in rest else file
        lines.append(f"    {k!r}: ({local!r}, {qs.videos[k].get('handoff')!r}),")
    lines += ["}", "", "VIDEO_NAMES = {" + ", ".join(f"{k!r}: {qs.name(k)!r}" for k in keys) + "}", ""]
    domains = {k: data["videos"][k].get("domain", "") for k in keys}
    if any(domains.values()):
        lines += ["VIDEO_DOMAINS = {" + ", ".join(f"{k!r}: {v!r}" for k, v in domains.items()) + "}", ""]
    lines += ["# (번호, 영상, 유형, 질의, 정답 구간 목록[(시작초, 끝초)])", "QUERIES = ["]
    for num, key, typ, ko, gts in qs.queries:
        spans = ", ".join(f"({num_str(a)}, {num_str(b)})" for a, b in gts)
        lines.append(f"    ({num}, {key!r}, {typ!r}, {ko!r}, [{spans}]),")
    lines += ["]", ""]
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"저장: {out} (질의 {len(qs.queries)}개)", file=sys.stderr)
    else:
        sys.stdout.write(text)


def probe_duration(path: Path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, check=True)
        return round(float(r.stdout.strip()), 1)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def from_py(out):
    import query_set

    qs = query_set.load(None)
    videos = {}
    for k in qs.video_keys:
        info = qs.videos[k]
        try:
            duration = probe_duration(qs.video_path(k))
        except FileNotFoundError:
            duration = None
        file = info["file"] if "/" in info["file"] else f"{LOCAL_VIDEO_DIR}/{info['file']}"
        videos[k] = {"file": file, "name": qs.name(k), "domain": "", "duration": duration}
        if info.get("handoff"):
            videos[k]["handoff"] = info["handoff"]
    queries = [{"num": num, "video": key, "type": typ, "query": ko, "gt": [list(g) for g in gts]}
               for num, key, typ, ko, gts in qs.queries]
    data = {"format": FORMAT, "videos": videos, "queries": queries}
    out = Path(out)
    if out.exists():
        sys.exit(f"{out}이 이미 있습니다. 덮어쓰지 않으니 다른 이름을 쓰거나 지우고 다시 실행하세요")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"저장: {out} (질의 {len(queries)}개, 영상 {len(videos)}개). 분야(domain)는 비어 있으니 라벨링 도구에서 채우세요")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("to-py", help="라벨 JSON → queries.py 형식")
    p.add_argument("labels")
    p.add_argument("-o", "--out", help="출력 파일 (없으면 화면에 출력)")
    p = sub.add_parser("from-py", help="queries.py → 라벨 JSON")
    p.add_argument("-o", "--out", required=True)
    args = parser.parse_args()
    if args.cmd == "to-py":
        to_py(args.labels, args.out)
    else:
        from_py(args.out)


if __name__ == "__main__":
    main()
