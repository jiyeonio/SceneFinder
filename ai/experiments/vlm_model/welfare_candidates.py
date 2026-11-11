"""복지 안내 평가 영상 후보 수집 (YouTube Data API, 메타데이터만, 영상은 받지 않음).

공식 기관 채널(ID 고정)의 업로드 목록 전체(playlistItems, 1 unit/50개)에서
정책 키워드가 제목·설명에 있는 영상만 골라 길이·자막·임베드 여부를 붙인다(videos, 1 unit/50개).

    python ai/experiments/vlm_model/welfare_candidates.py --out docs/experiments/vlm_eval_candidates.tsv

YOUTUBE_API_KEY는 backend/.env에서 읽는다(출력하지 않음).
"""
import argparse, csv, os, re, sys, time
from pathlib import Path

import requests
from dotenv import load_dotenv

API = "https://www.googleapis.com/youtube/v3"

# (채널 이름, 채널 ID, 기관 구분). 이름 검색은 비공식 채널이 먼저 잡혀서(예: 「보건복지부」→ 업로드 1개 채널) ID로 고정.
# 구독자 수·업로드 수·핸들을 보고 공식 채널로 판단한 것만 넣음. 공식 여부가 불확실한 채널(예: 기초연금TV)은 뺌.
CHANNELS = [
    ("보건복지부TV", "UCRsetXyMdNsR4M9KvA-a_fg", "중앙부처"), ("복지로", "UCQQpfWhl9_eM0RKwqEg_4vQ", "공공기관"),
    ("한국사회보장정보원", "UCqywafpjY-pK74nO8ZL9R3Q", "공공기관"), ("국민연금TV", "UCqNLvq_8xZM0hhw-spFnLQg", "공공기관"),
    ("국민건강보험", "UC7tsTpx4Ra-oJrjIb9ItBUA", "공공기관"), ("근로복지공단", "UCPHSl6Wko6Bg6-i42suzTAA", "공공기관"),
    ("고용노동부", "UC_fFLoUU8NzaZ0G7jlE1DQA", "중앙부처"), ("국토교통부", "UC0G0Z05LATPtpUkxeOrEjOA", "중앙부처"),
    ("성평등가족부", "UCcgeHR34Rr17yaoaqD0jR2A", "중앙부처"), ("여가부아이돌봄서비스", "UClJ0_7DpmRwQTsYZ2NqIQAA", "중앙부처"),
    ("행정안전부", "UCzteSXznVjwESizsCcSKSWw", "중앙부처"), ("국세청", "UCVTdK_EozBDQ7ICMPJdbpzQ", "중앙부처"),
    ("LH 한국토지주택공사", "UCzCH27zxNFmbzultWL4u-bw", "공공기관"), ("서울시", "UCZUPZW5idAxYp-Asj__lVAA", "지자체"),
    ("서울시아이돌봄", "UCwoRGJIeUDg8NuIYnYSrayg", "지자체"), ("경기도청", "UCIuDua3JS1-m9zi4CuAqBVw", "지자체"),
    ("부산광역시", "UC35SH2IZCoDAyjdM_BKNVlA", "지자체"),
]

# 정책 → 제목·설명에서 찾을 키워드
POLICIES = {
    "기초연금": ["기초연금"],
    "아이돌봄": ["아이돌봄"],
    "청년주거": ["청년월세", "청년 월세", "청년주거", "청년 주거", "전세임대", "행복주택"],
    "국민연금": ["국민연금", "연금 수령", "노령연금"],
    "부모급여·아동수당": ["부모급여", "아동수당", "첫만남"],
    "주거·생계·의료급여": ["주거급여", "생계급여", "의료급여", "기초생활"],
    "실업급여·취업지원": ["실업급여", "구직급여", "국민취업지원"],
    "근로·자녀장려금": ["근로장려금", "자녀장려금"],
    "장애인": ["장애인 등록", "장애인연금", "활동지원"],
    "장기요양·돌봄": ["장기요양", "노인맞춤돌봄", "돌봄"],
    "긴급복지·바우처": ["긴급복지", "에너지바우처", "문화누리"],
}
HOWTO = re.compile(r"신청|방법|절차|하는 법|따라하기|안내|서류|조회|화면")


def get(path, key, **params):
    for _ in range(3):
        r = requests.get(f"{API}/{path}", params={**params, "key": key}, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(2)
    r.raise_for_status()


def iso_sec(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-sec", type=int, default=90)
    ap.add_argument("--max-sec", type=int, default=1200)
    a = ap.parse_args()
    load_dotenv(Path(__file__).resolve().parents[3] / "backend" / ".env")
    key = os.getenv("YOUTUBE_API_KEY") or sys.exit("YOUTUBE_API_KEY 없음")

    rows, chan_log = [], []
    for q, cid, kind in CHANNELS:
        ch = get("channels", key, part="snippet,contentDetails,statistics", id=cid)["items"][0]
        ctitle = ch["snippet"]["title"]
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        vids, token = [], None
        while True:
            pl = get("playlistItems", key, part="snippet", playlistId=uploads, maxResults=50, **({"pageToken": token} if token else {}))
            for it in pl["items"]:
                sn = it["snippet"]; text = sn["title"] + " " + sn.get("description", "")[:300]
                pol = [p for p, kws in POLICIES.items() if any(k in text for k in kws)]
                if pol and HOWTO.search(sn["title"]):
                    vids.append((sn["resourceId"]["videoId"], sn["title"], sn["publishedAt"][:10], pol))
            token = pl.get("nextPageToken")
            if not token:
                break
        chan_log.append((q, ctitle, cid, int(ch["statistics"].get("videoCount", 0))))
        for i in range(0, len(vids), 50):
            chunk = vids[i:i + 50]
            meta = {v["id"]: v for v in get("videos", key, part="contentDetails,status,statistics", id=",".join(x[0] for x in chunk))["items"]}
            for vid, title, pub, pol in chunk:
                m = meta.get(vid)
                if not m:
                    continue
                sec = iso_sec(m["contentDetails"]["duration"])
                if sec is None or not (a.min_sec <= sec <= a.max_sec):
                    continue
                rows.append({
                    "youtube_id": vid, "channel": ctitle, "channel_id": cid, "kind": kind, "policy": "|".join(pol),
                    "title": title.replace("\t", " "), "published": pub, "duration_sec": sec,
                    "caption": m["contentDetails"].get("caption"), "embeddable": m["status"].get("embeddable"),
                    "license": m["status"].get("license"), "views": m["statistics"].get("viewCount"),
                })
        print(f"{q} → {ctitle} ({cid}): 업로드 {chan_log[-1][3]}, 후보 {sum(r['channel_id'] == cid for r in rows)}", flush=True)

    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader(); w.writerows(sorted(rows, key=lambda r: (r["channel"], r["policy"], r["published"])))
    print(f"후보 {len(rows)}개 → {a.out}")


if __name__ == "__main__":
    main()
