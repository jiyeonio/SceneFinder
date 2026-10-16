"""영상 분석 상태 테이블(videos, video_features)만 현재 DB에서 내보내고 새 DB로 가져옵니다.

    # 1) 내보내기: backend/.env의 DB(지금 쓰는 팀 DB)에서 읽기만 함. 저장 위치는 레포 밖
    python tools/supabase/analysis_state.py export [--out ~/scenefinder_supabase_export]

    # 2) 가져오기 확인(기본, 새 DB에 아무것도 쓰지 않음): 파일 검사와 할 일만 출력
    python tools/supabase/analysis_state.py import --in ~/scenefinder_supabase_export/<시각>

    # 3) 실제로 가져오기: backend/.env.new의 DB에 씀
    python tools/supabase/analysis_state.py import --in ~/scenefinder_supabase_export/<시각> --apply

- 회원(auth)·검색 기록(search_history)·즐겨찾기(favorites)는 옮기지 않습니다.
- 새 DB 접속 정보는 backend/.env.new의 SUPABASE_URL·SUPABASE_SERVICE_KEY에서 읽습니다. backend/.env는 읽기만 합니다.
- 새 DB가 backend/.env와 같은 DB면 거부합니다. 키·URL 값은 출력하지 않습니다.
- 새 DB에는 docs/supabase/schema.sql을 먼저 실행해 두어야 합니다.
- video_id(uuid)와 video_features.id를 그대로 옮겨 외래키가 유지됩니다. 같은 키가 있으면 덮어씁니다(upsert).
- 분석 중(PROCESSING)이던 영상은 새 서버에서 이어서 처리되지 않으므로 기본으로 PENDING으로 바꿔 넣습니다(--keep-processing으로 끔).
- feature 파일과 자막 파일은 DB가 아니라 서버 디스크(data/features, data/processed/subtitles)에 있습니다. 같은 서버에서 쓰면 그대로 됩니다.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ENV = ROOT / "backend" / ".env"
TARGET_ENV = ROOT / "backend" / ".env.new"
TABLES = ("videos", "video_features")      # 이 순서로 넣음 (외래키)
CONFLICT_KEY = {"videos": "video_id", "video_features": "id"}
PAGE = 1000
BATCH = 200


def read_env(path):
    from dotenv import dotenv_values
    if not path.exists():
        sys.exit(f"{path.relative_to(ROOT)} 파일이 없습니다")
    v = dotenv_values(path)
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY") if not v.get(k)]
    if missing:
        sys.exit(f"{path.relative_to(ROOT)}에 {', '.join(missing)} 값이 없습니다")
    return v["SUPABASE_URL"].rstrip("/"), v["SUPABASE_SERVICE_KEY"]


def client(url, key):
    from supabase import create_client
    return create_client(url, key)


def forbidden_dirs():
    """export를 두면 안 되는 곳: 레포와, 레포 안 심볼릭 링크(data·models 등)가 가리키는 원본 폴더."""
    dirs = {ROOT.resolve()}
    for p in ROOT.rglob("*"):
        if any(part in (".git", "node_modules", ".venv") for part in p.relative_to(ROOT).parts[:-1]):
            continue
        if p.is_symlink():
            dirs.add(p.resolve())
    return dirs


def out_allowed(out: Path) -> bool:
    """경로 그대로(심볼릭 링크를 따라가기 전)와 실제 경로 모두 레포·원본 폴더 밖이어야 함."""
    lexical = Path(os.path.abspath(out.expanduser()))
    real = out.expanduser().resolve()
    if lexical == ROOT or ROOT in lexical.parents:
        return False
    return not any(real == d or d in real.parents for d in forbidden_dirs())


def export(out_root: Path):
    if not out_allowed(out_root):
        sys.exit("export 파일은 레포 밖(레포의 data·models 등 링크가 가리키는 원본 폴더도 안 됨)에 저장해야 합니다 (--out)")
    out_root = out_root.expanduser().resolve()
    out = out_root / time.strftime("%Y%m%d_%H%M%S")
    out.mkdir(parents=True)
    sb = client(*read_env(SOURCE_ENV))
    manifest = {"exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "source": "backend/.env", "tables": {}}
    for t in TABLES:
        rows, start = [], 0
        while True:
            page = sb.table(t).select("*").order(CONFLICT_KEY[t]).range(start, start + PAGE - 1).execute().data
            rows += page
            if len(page) < PAGE:
                break
            start += PAGE
        with open(out / f"{t}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        manifest["tables"][t] = len(rows)
        print(f"{t}: {len(rows)}행")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    out.chmod(0o700)
    print("저장:", out)


def load_export(folder: Path):
    folder = folder.expanduser().resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    data = {}
    for t in TABLES:
        with open(folder / f"{t}.jsonl", encoding="utf-8") as f:
            data[t] = [json.loads(line) for line in f if line.strip()]
        if len(data[t]) != manifest["tables"][t]:
            sys.exit(f"{t}: 파일 행 수({len(data[t])})가 manifest({manifest['tables'][t]})와 다릅니다")
    return manifest, data


def check(data, keep_processing=False):
    """가져오기 전 검사. (문제 목록, 바꿀 내용 요약)"""
    problems, notes = [], []
    vids = [r["video_id"] for r in data["videos"]]
    if len(vids) != len(set(vids)):
        problems.append("videos.video_id 중복")
    yids = [r["youtube_video_id"] for r in data["videos"] if r.get("youtube_video_id")]
    if len(yids) != len(set(yids)):
        problems.append("videos.youtube_video_id 중복 (새 DB의 고유 인덱스에 걸림)")
    fids = [r["id"] for r in data["video_features"]]
    if len(fids) != len(set(fids)):
        problems.append("video_features.id 중복")
    orphan = [r["id"] for r in data["video_features"] if r["video_id"] not in set(vids)]
    if orphan:
        problems.append(f"videos에 없는 video_id를 가리키는 video_features {len(orphan)}개")
    processing = sum(1 for r in data["videos"] if r["status"] == "PROCESSING")
    if processing and not keep_processing:
        notes.append(f"PROCESSING {processing}개를 PENDING으로 바꿔 넣음")
    return problems, notes


def import_(folder: Path, apply: bool, keep_processing: bool):
    manifest, data = load_export(folder)
    print("export 시각:", manifest["exported_at"], "|", ", ".join(f"{t} {n}행" for t, n in manifest["tables"].items()))
    problems, notes = check(data, keep_processing)
    for n in notes:
        print("-", n)
    if problems:
        sys.exit("문제가 있어 가져오지 않습니다: " + "; ".join(problems))
    target = read_env(TARGET_ENV)
    if SOURCE_ENV.exists() and read_env(SOURCE_ENV)[0] == target[0]:
        sys.exit("backend/.env.new가 backend/.env와 같은 DB를 가리킵니다. 새 프로젝트 값을 넣었는지 확인하세요")
    if not keep_processing:
        for r in data["videos"]:
            if r["status"] == "PROCESSING":
                r["status"] = "PENDING"
    if not apply:
        print("확인만 했습니다(dry-run). 새 DB에 쓰려면 --apply를 붙이세요.")
        return
    sb = client(*target)
    for t in TABLES:
        rows = data[t]
        for i in range(0, len(rows), BATCH):
            sb.table(t).upsert(rows[i:i + BATCH], on_conflict=CONFLICT_KEY[t]).execute()
        got = sb.table(t).select("*", count="exact", head=True).execute().count
        print(f"{t}: {len(rows)}행 넣음, 새 DB 전체 {got}행")
    print("마지막으로 새 프로젝트 SQL Editor에서 아래를 실행해 video_features.id 번호를 이어지게 하세요:")
    print("  select setval(pg_get_serial_sequence('public.video_features', 'id'), "
          "(select coalesce(max(id), 1) from public.video_features));")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("export", help="backend/.env의 DB에서 내보내기 (읽기만)")
    p.add_argument("--out", default=str(Path.home() / "scenefinder_supabase_export"))
    p = sub.add_parser("import", help="backend/.env.new의 DB로 가져오기 (기본은 확인만)")
    p.add_argument("--in", dest="folder", required=True)
    p.add_argument("--apply", action="store_true", help="실제로 새 DB에 씀")
    p.add_argument("--keep-processing", action="store_true", help="PROCESSING 상태를 그대로 넣음")
    args = parser.parse_args()
    if args.cmd == "export":
        export(Path(args.out))
    else:
        import_(Path(args.folder), args.apply, args.keep_processing)


if __name__ == "__main__":
    main()
