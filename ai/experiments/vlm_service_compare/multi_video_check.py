"""「한 검색 요청에 영상 5개」 분석을 설명문 끔·켬으로 돌려 영상별 INDEXED 시간을 잽니다.

서비스의 POST /api/search/multi는 한 요청에서 분석할 영상들의 run_indexing을 같은 BackgroundTasks에 넣고,
FastAPI(Starlette)는 이를 한 스레드에서 차례로 실행합니다. 이 스크립트는 그와 같게 run_indexing을 차례로 부릅니다.
YouTube에서 받지 않도록 download_video만 로컬 파일 복사로 바꿔서(--work 폴더), 내려받은 파일을 지우는 경로까지 그대로 탑니다.

    CAPTION_SEARCH_ENABLED=0 python ai/experiments/vlm_service_compare/multi_video_check.py --label off \
        --videos ~/scenefinder_eval/videos --work /tmp/... --out ~/scenefinder_eval/vlm_service 36h_8hJiO50 ...

- 같은 GPU를 쓰는 백엔드는 끄고 실행 (Whisper·Qwen 메모리)
- INDEXED·설명문 상태는 DB를 0.5초마다 조회해 기록 (요청 시작 기준 초)
- 켬이면 설명문이 모두 끝날(READY/FAILED/PENDING) 때까지 기다리고, 그동안 --work 폴더에 남은 영상 파일 용량을 기록
"""
import argparse
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--videos", required=True, help="<유튜브ID>.mp4가 있는 폴더")
    ap.add_argument("--work", required=True, help="'내려받은' 파일을 둘 빈 폴더 (분석 후 지워지는지 확인)")
    ap.add_argument("--out", required=True)
    ap.add_argument("ids", nargs="+")
    a = ap.parse_args()

    from backend.services import captions, indexer

    src, work = Path(a.videos).expanduser(), Path(a.work).expanduser()
    work.mkdir(parents=True, exist_ok=True)

    def fake_download(youtube_video_id, out_dir=None):
        dst = work / f"{youtube_video_id}.mp4"
        shutil.copyfile(src / f"{youtube_video_id}.mp4", dst)
        return str(dst)
    indexer.download_video = fake_download

    rows = {yid: indexer.get_video(yid) for yid in a.ids}
    vids = {yid: r["video_id"] for yid, r in rows.items()}
    for yid in a.ids:
        r = indexer.prepare(yid, rows[yid]["title"], force=True)
        assert r["state"] == "STARTED", (yid, r)

    t0 = time.perf_counter()
    rec = {yid: {} for yid in a.ids}
    held = []
    stop = threading.Event()

    def poll():
        db = indexer.supabase
        while not stop.is_set():
            now = round(time.perf_counter() - t0, 1)
            vs = db.table("videos").select("video_id,status").in_("video_id", list(vids.values())).execute().data
            cs = db.table("video_captions").select("video_id,status").in_("video_id", list(vids.values())).execute().data
            vmap = {r["video_id"]: r["status"] for r in vs}
            cmap = {r["video_id"]: r["status"] for r in cs}
            for yid, vid in vids.items():
                if vmap.get(vid) == "INDEXED" and "indexed" not in rec[yid]:
                    rec[yid]["indexed"] = now
                st = cmap.get(vid)
                if st and "indexed" in rec[yid] and st != rec[yid].get("caption_last"):
                    rec[yid]["caption_last"] = st
                    rec[yid][f"caption_{st}"] = now
            held.append((now, sum(p.stat().st_size for p in work.glob("*.mp4"))))
            time.sleep(0.5)

    th = threading.Thread(target=poll, daemon=True)
    th.start()
    returned = {}
    for yid in a.ids:   # BackgroundTasks와 같이 한 스레드에서 차례로
        indexer.run_indexing(vids[yid], yid)
        returned[yid] = round(time.perf_counter() - t0, 1)

    if captions.enabled():
        while True:
            snap = captions.QUEUE.snapshot()
            if snap["running"] is None and not snap["waiting"]:
                break
            time.sleep(1)
    time.sleep(2)
    stop.set()
    th.join()

    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    result = {"label": a.label, "caption_enabled": captions.enabled(), "ids": a.ids,
              "returned_sec": returned, "videos": rec,
              "held_max_mb": round(max(b for _, b in held) / 2**20, 1),
              "held_end_mb": round(held[-1][1] / 2**20, 1),
              "left_files": sorted(p.name for p in work.glob("*.mp4"))}
    (out / f"multi_{a.label}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
