"""평가셋 검수 파일 관리 (검수자 1명, 파일 하나). dev 8개를 먼저, test 8개는 뒤에 둔다.

질의 출처(origin)는 두 가지이고 결과도 따로 보고한다:
- ai_draft: 화면·자막을 보고 AI가 쓴 초안 질의 (S/V/정답 없음)
- simulated_user: 영상 제목·채널·정책만 보고 AI가 실제 사용자처럼 쓴 질문. 정답 구간은 따로 AI가 영상을 보고 초안을 만듦
검수 상태(source)는 ai_draft(미검수) → human_reviewed(검수 완료).

    python ai/experiments/vlm_model/review_set.py init                  # 영상만 등록한 review.json
    python ai/experiments/vlm_model/review_set.py merge --origin ai_draft --keys dev01,...   # 초안 합치기
    python ai/experiments/vlm_model/review_set.py merge --origin simulated_user --keys dev01,...
    python ai/experiments/vlm_model/review_set.py status                # 검수 목록 갱신
"""
import argparse, csv, json, shutil, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPLIT = ROOT / "docs/experiments/vlm_eval_split.tsv"
LABEL_DIR = ROOT / "ai/experiments/vlm_model/labels"
LABELS = LABEL_DIR / "review.json"
REVIEW_TSV = ROOT / "docs/experiments/vlm_eval_review.tsv"
DATA = Path("/nfs/team/data/scenefinder_vlm")
DRAFT_DIRS = {"ai_draft": DATA / "ai_drafts", "simulated_user": DATA / "sim_drafts"}
FORMAT = "scenefinder-labels/1"
NUM_BASE = {"ai_draft": 1000, "simulated_user": 5000}   # 출처별 질의 번호 대역
# 예상 시간(분): 영상 훑어보기(길이의 0.6배) + 정답 있는 초안 1개당 2분(자막만 언급 구간이 있으면 +1분) + 정답 없음 1개당 1분
WATCH_RATIO, DRAFT_MIN, SO_MIN, NEG_MIN = 0.6, 2, 1, 1


def split_rows():
    rows = list(csv.DictReader(open(SPLIT), delimiter="\t"))
    return {r["key"]: r for r in sorted(rows, key=lambda r: (r["split"] != "dev", r["key"]))}


def load():
    return json.loads(LABELS.read_text(encoding="utf-8"))


def write(data):
    if LABELS.exists():
        shutil.copy(LABELS, LABELS.with_suffix(".json.bak"))
    LABELS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_init(a):
    rows = split_rows()
    if LABELS.exists() and not a.force:
        sys.exit("review.json 있음 (--force로 다시 만듦)")
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    videos = {k: {"youtube_id": r["youtube_id"], "name": k, "domain": "복지", "title": r["title"],
                  "duration": float(r["duration_sec"]), "split": r["split"]} for k, r in rows.items()}
    write({"format": FORMAT, "videos": videos, "queries": [], "negative_queries": [], "meta": {"merged": {}}})
    # 라벨링 도구용 영상 목록 (이 순서대로 보임: dev 먼저)
    with open(LABEL_DIR / "review_videos.tsv", "w", newline="") as f:
        w = csv.writer(f, delimiter="\t"); w.writerow(["youtube_id", "key", "title", "domain"])
        for k, r in rows.items():
            w.writerow([r["youtube_id"], k, f"[{r['split']}] {r['title']}", "복지"])
    print(f"review.json: 영상 {len(videos)}개")
    cmd_status(a)


def draft(origin, key):
    p = DRAFT_DIRS[origin] / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cmd_merge(a):
    data = load(); origin = a.origin
    merged = data["meta"].setdefault("merged", {}).setdefault(origin, [])
    keys = [k for k in a.keys.split(",") if k]
    for k in keys:
        if k in merged:
            print(f"{k}: {origin} 이미 합침, 건너뜀"); continue
        d = draft(origin, k)
        if d is None:
            sys.exit(f"{k}: {origin} 초안 파일 없음 ({DRAFT_DIRS[origin]})")
        used = [q["num"] for q in data["queries"] + data["negative_queries"]]
        base = NUM_BASE[origin] + list(split_rows()).index(k) * 100   # 영상마다 100번 대역
        num = max([n for n in used if base <= n < base + 100] + [base])
        for q in d["queries"]:
            num += 1
            item = {"num": num, "video": k, "type": q["type"], "query": q["query"], "gt": q["gt"],
                    "overlay_text": bool(q.get("overlay_text")),
                    "subtitle_only_spans": q.get("subtitle_only_spans", []) if q["type"] == "V" else [],
                    "source": "ai_draft", "origin": origin, "note": q.get("note", "")}
            if q.get("persona"):
                item["persona"] = q["persona"]
            data["queries"].append(item)
        for q in d["negatives"]:
            num += 1
            item = {"num": num, "video": k, "query": q["query"], "gt": [], "source": "ai_draft", "origin": origin,
                    "note": q.get("note", "")}
            if q.get("persona"):
                item["persona"] = q["persona"]
            data["negative_queries"].append(item)
        merged.append(k)
        print(f"{k}: {origin} 질의 {len(d['queries'])}개 + 정답 없음 {len(d['negatives'])}개 합침")
    data["meta"]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write(data)
    cmd_status(a)


def cmd_status(a):
    rows = split_rows(); data = load()
    out = []
    for k, r in rows.items():
        dur = float(r["duration_sec"])
        row = {"split": r["split"], "key": k, "youtube_id": r["youtube_id"], "title": r["title"],
               "duration": f"{int(dur) // 60}:{int(dur) % 60:02d}", "subtitle_source": r.get("subtitle_source", "")}
        est = WATCH_RATIO * dur / 60
        for origin, label in (("ai_draft", "AI초안"), ("simulated_user", "사용자질문")):
            qs = [q for q in data["queries"] + data["negative_queries"] if q["video"] == k and q.get("origin") == origin]
            done = sum(q.get("source") == "human_reviewed" for q in qs)
            row[f"{label}_합침"] = len(qs) if qs else ""
            row[f"{label}_검수완료"] = f"{done}/{len(qs)}" if qs else ""
            est += sum((DRAFT_MIN + (SO_MIN if q.get("subtitle_only_spans") else 0)) if q.get("gt") else NEG_MIN for q in qs)
        row["예상_분"] = round(est)
        out.append(row)
    with open(REVIEW_TSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]), delimiter="\t"); w.writeheader(); w.writerows(out)
    for sp in ("dev", "test"):
        mine = [o for o in out if o["split"] == sp]
        print(f"{sp}: 영상 {len(mine)}개, 예상 {sum(o['예상_분'] for o in mine)}분")
    print(f"→ {REVIEW_TSV.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_init)
    p = sub.add_parser("merge"); p.add_argument("--origin", choices=list(DRAFT_DIRS), required=True)
    p.add_argument("--keys", required=True); p.set_defaults(f=cmd_merge)
    sub.add_parser("status").set_defaults(f=cmd_status)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
