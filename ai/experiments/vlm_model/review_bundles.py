"""평가셋 검수 묶음 관리 (팀원 3명, 영상 단위 3묶음).

순서를 도구로 강제한다: 검수자가 영상마다 직접 질문(human_written)을 쓴 뒤에만 AI 초안을 합친다.

    # 1) 묶음 라벨 파일(영상만, 질의 없음)과 검수 목록 만들기
    python ai/experiments/vlm_model/review_bundles.py init
    # 2) 검수 목록 갱신 (직접 쓴 질문·AI 초안·검수 진행 상황, 예상 시간)
    python ai/experiments/vlm_model/review_bundles.py status
    # 3) 묶음의 모든 영상에 직접 쓴 질문이 1개 이상 있으면 AI 초안을 합침
    python ai/experiments/vlm_model/review_bundles.py merge --bundle 1

AI 초안은 저장소 밖(/nfs/team/data/scenefinder_vlm/ai_drafts/<key>.json)에 두고, 합치기 전에는 검수자에게 보이지 않는다.
"""
import argparse, csv, json, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPLIT = ROOT / "docs/experiments/vlm_eval_split.tsv"
LABEL_DIR = ROOT / "ai/experiments/vlm_model/labels"
REVIEW_TSV = ROOT / "docs/experiments/vlm_eval_review.tsv"
DRAFTS = Path("/nfs/team/data/scenefinder_vlm/ai_drafts")
EVAL_VIDEOS = Path("/nfs/team/data/scenefinder_vlm/eval_videos")
FORMAT = "scenefinder-labels/1"

# 영상 단위 3묶음: 묶음마다 dev·test 영상과 총 길이를 비슷하게 (dev 약 18분 + test 약 22분)
BUNDLES = {
    1: ["dev05", "dev02", "test01"],
    2: ["dev01", "dev03", "dev06", "test08", "test06", "test02"],
    3: ["dev04", "dev07", "dev08", "test07", "test05", "test04", "test03"],
}
# 예상 시간(분) 계산 규칙: 1단계 = 영상 훑어보기(길이의 0.6배) + 직접 질문 2개 × 4분,
# 2단계 = 정답 있는 AI 초안 1개당 2분(+자막만 언급 구간이 있으면 1분) + 정답 없음 1개당 1분
WATCH_RATIO, HUMAN_Q_MIN, HUMAN_Q_N, DRAFT_MIN, SO_MIN, NEG_MIN = 0.6, 4, 2, 2, 1, 1


def split_rows():
    return {r["key"]: r for r in csv.DictReader(open(SPLIT), delimiter="\t")}


def bundle_of(key):
    return next(b for b, ks in BUNDLES.items() if key in ks)


def label_path(b):
    return LABEL_DIR / f"bundle{b}.json"


def load(b):
    return json.loads(label_path(b).read_text(encoding="utf-8"))


def write(b, data):
    p = label_path(b)
    if p.exists():
        shutil.copy(p, p.with_suffix(".json.bak"))
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def human_written(q):
    return q.get("source") in ("human_written", "human")


def cmd_init(a):
    rows = split_rows()
    assert sorted(k for ks in BUNDLES.values() for k in ks) == sorted(rows), "묶음에 빠지거나 겹친 영상"
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    for b, keys in BUNDLES.items():
        if label_path(b).exists() and not a.force:
            print(f"bundle{b}.json 있음, 건너뜀 (--force로 다시 만듦)"); continue
        videos = {k: {"youtube_id": rows[k]["youtube_id"], "name": k, "domain": "복지", "title": rows[k]["title"],
                      "duration": float(rows[k]["duration_sec"]), "split": rows[k]["split"]} for k in keys}
        write(b, {"format": FORMAT, "videos": videos, "queries": [], "negative_queries": [],
                  "meta": {"bundle": b, "ai_drafts_merged": False}})
        print(f"bundle{b}.json: 영상 {len(keys)}개")
    # 라벨링 도구용: 묶음 영상만 담은 YouTube 목록(키가 youtube_id로 연결됨)과 묶음 영상만 있는 폴더(심볼릭 링크)
    for b, keys in BUNDLES.items():
        with open(LABEL_DIR / f"bundle{b}_videos.tsv", "w", newline="") as f:
            w = csv.writer(f, delimiter="\t"); w.writerow(["youtube_id", "key", "title", "domain"])
            for k in keys:
                w.writerow([rows[k]["youtube_id"], k, rows[k]["title"], "복지"])
        d = EVAL_VIDEOS.parent / f"eval_videos_bundle{b}"; d.mkdir(exist_ok=True)
        for k in keys:
            link = d / f"{rows[k]['youtube_id']}.mp4"
            if not link.exists():
                link.symlink_to(EVAL_VIDEOS / link.name)
    cmd_status(a)


def draft_of(key):
    p = DRAFTS / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cmd_status(a):
    rows = split_rows()
    out = []
    for b, keys in BUNDLES.items():
        data = load(b)
        for k in keys:
            r = rows[k]; dur = float(r["duration_sec"])
            hq = [q for q in data["queries"] if q["video"] == k and human_written(q)]
            d = draft_of(k)
            dq = d["queries"] if d else []
            dn = d["negatives"] if d else []
            merged = [q for q in data["queries"] + data["negative_queries"] if q["video"] == k and q.get("source") in ("ai_draft", "human_reviewed")]
            done = sum(q.get("source") == "human_reviewed" for q in merged)
            step1 = WATCH_RATIO * dur / 60 + HUMAN_Q_N * HUMAN_Q_MIN
            step2 = sum(DRAFT_MIN + (SO_MIN if q.get("subtitle_only_spans") else 0) for q in dq) + NEG_MIN * len(dn)
            out.append({
                "bundle": b, "reviewer": "", "split": r["split"], "key": k, "youtube_id": k and r["youtube_id"],
                "title": r["title"], "duration": f"{int(dur) // 60}:{int(dur) % 60:02d}",
                "subtitle_source": r.get("subtitle_source", ""),
                "1단계_직접질문1": hq[0]["query"] if len(hq) > 0 else "",
                "1단계_직접질문2": hq[1]["query"] if len(hq) > 1 else "",
                "1단계_완료": "O" if hq else "",
                "2단계_AI초안": f"S{sum(q['type'] == 'S' for q in dq)}/V{sum(q['type'] == 'V' for q in dq)}/없음{len(dn)}" if d else "작성 중",
                "2단계_합침": "O" if data["meta"].get("ai_drafts_merged") else "",
                "2단계_검수완료": f"{done}/{len(merged)}" if merged else "",
                "예상_1단계_분": round(step1), "예상_2단계_분": round(step2) if d else "",
            })
    with open(REVIEW_TSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t"); w.writeheader(); w.writerows(out)
    for b in BUNDLES:
        mine = [o for o in out if o["bundle"] == b]
        s1 = sum(o["예상_1단계_분"] for o in mine); s2 = sum(o["예상_2단계_분"] or 0 for o in mine)
        print(f"묶음 {b}: 영상 {len(mine)}개, 직접 질문 완료 {sum(o['1단계_완료'] == 'O' for o in mine)}/{len(mine)}, "
              f"예상 1단계 {s1}분 + 2단계 {s2}분 = 약 {(s1 + s2) / 60:.1f}시간")
    print(f"→ {REVIEW_TSV.relative_to(ROOT)}")


def cmd_merge(a):
    b = a.bundle; data = load(b)
    if data["meta"].get("ai_drafts_merged"):
        sys.exit(f"묶음 {b}: 이미 합침")
    missing = [k for k in BUNDLES[b] if not any(q["video"] == k and human_written(q) for q in data["queries"])]
    if missing:
        sys.exit(f"묶음 {b}: 직접 쓴 질문이 없는 영상 {missing} → 먼저 영상마다 1~2개씩 직접 쓰세요")
    nodraft = [k for k in BUNDLES[b] if draft_of(k) is None]
    if nodraft:
        sys.exit(f"묶음 {b}: AI 초안이 아직 없는 영상 {nodraft}")
    num = max([q["num"] for q in data["queries"] + data["negative_queries"]] + [b * 1000])
    for k in BUNDLES[b]:
        d = draft_of(k)
        for q in d["queries"]:
            num += 1
            data["queries"].append({"num": num, "video": k, "type": q["type"], "query": q["query"],
                                    "gt": q["gt"], "overlay_text": bool(q.get("overlay_text")),
                                    "subtitle_only_spans": q.get("subtitle_only_spans", []) if q["type"] == "V" else [],
                                    "source": "ai_draft", "note": q.get("note", "")})
        for q in d["negatives"]:
            num += 1
            data["negative_queries"].append({"num": num, "video": k, "query": q["query"], "gt": [],
                                             "source": "ai_draft", "note": q.get("note", "")})
    data["meta"].update(ai_drafts_merged=True, merged_at=datetime.now().isoformat(timespec="seconds"))
    write(b, data)
    print(f"묶음 {b}: AI 초안을 합쳤습니다")
    cmd_status(a)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_init)
    sub.add_parser("status").set_defaults(f=cmd_status)
    p = sub.add_parser("merge"); p.add_argument("--bundle", type=int, required=True); p.set_defaults(f=cmd_merge)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
