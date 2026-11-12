"""화면 검색 LoRA 학습용 복지 영상 후보 수집과 선택 (YouTube Data API 메타데이터만, 영상은 받지 않음).

평가(dev·test) 채널이 아닌 공식 기관 채널만 쓴다(vlm_model_plan.md 「평가 영상과 학습 영상 분리」).
welfare_candidates.py의 수집 코드를 그대로 쓰고 채널·정책 목록만 학습용으로 바꾼다.

    python ai/experiments/vlm_model/lora_candidates.py collect --out docs/experiments/vlm_lora_candidates.tsv
    python ai/experiments/vlm_model/lora_candidates.py select --cand docs/experiments/vlm_lora_candidates.tsv \
        --out docs/experiments/vlm_lora_train_videos.tsv --n 20
"""
import argparse, csv, re, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import welfare_candidates as wc

DOCS = Path(__file__).resolve().parents[3] / "docs/experiments"

# 평가에 쓰지 않은 공식 채널 (채널 검색 결과에서 구독자 수·업로드 수·핸들로 공식 채널로 판단한 것만, 2026-11-12)
CHANNELS = [
    ("한국사회보장정보원", "UCqywafpjY-pK74nO8ZL9R3Q", "공공기관"), ("성평등가족부", "UCcgeHR34Rr17yaoaqD0jR2A", "중앙부처"),
    ("여가부아이돌봄서비스", "UClJ0_7DpmRwQTsYZ2NqIQAA", "중앙부처"), ("행정안전부", "UCzteSXznVjwESizsCcSKSWw", "중앙부처"),
    ("경기도청", "UCIuDua3JS1-m9zi4CuAqBVw", "지자체"), ("부산광역시", "UC35SH2IZCoDAyjdM_BKNVlA", "지자체"),
    ("한국장애인개발원", "UCaxUtajlV9xvwmPTE40EaTw", "공공기관"), ("한국자활복지개발원", "UCMtpj9AdMF2lNrMzDRGBmaQ", "공공기관"),
    ("한국노인인력개발원", "UCE2ll9PlDk38VJlEIc8yhnA", "공공기관"), ("HUG 주택도시보증공사", "UCXXERp2lKuALHbyuXIpLqzw", "공공기관"),
    ("한국주택금융공사", "UCw00vX9nr7gRFYI4BpHEWig", "공공기관"), ("한국고용정보원", "UCuvWZ93qXlvEtCEkLxS0eDg", "공공기관"),
    ("서울시복지재단", "UCnWf50K_zrZAPDoUFiHtnwQ", "공공기관"), ("중소벤처기업부", "UCaiBniKLomFVHcb5zt3lnfQ", "중앙부처"),
    ("교육부", "UCexUyFaq9YH7XJfCQzVR_jg", "중앙부처"), ("한국장학재단", "UC4ZFdxlb7pT2kj9DDnemDGQ", "공공기관"),
    ("국가보훈부", "UClvT0GWxHHznabonSbWf7cg", "중앙부처"), ("한국에너지공단", "UCsgwaqE9DNxWV8qlTN2GYjQ", "공공기관"),
    ("국민권익위원회", "UCUAYkowhhWi7W5EPHpSO_gg", "중앙부처"), ("세종특별자치시", "UCosgR0a4guwZ_BwiV-c5U8w", "지자체"),
    ("충청북도청", "UCXiv1QlLhil_qGtFPaEtLDQ", "지자체"), ("전북특별자치도", "UCgciFvhDgtOBu6ieoE9zdhg", "지자체"),
    ("경상남도", "UCiGeWRkwZJL1ZH_1ImaZwmg", "지자체"), ("제주특별자치도", "UCK2JegInDWoDtwEpjh4HzLg", "지자체"),
]

# 평가 정책 + 학습용으로 더한 생활 지원 정책 (화면·말투 다양성)
POLICIES = dict(wc.POLICIES) | {
    "학자금·장학금": ["학자금", "장학금", "국가장학"],
    "노인일자리": ["노인일자리", "노인 일자리"],
    "전세보증·주택연금": ["전세보증", "보증보험", "주택연금", "디딤돌", "버팀목"],
    "보훈": ["보훈급여", "국가유공자", "보훈"],
    "자활·고용": ["자활", "내일배움", "고용24", "워크넷", "청년도약"],
    "정부24·민원": ["정부24", "보조금24", "민원"],
}


# 신청·조회 화면이 나올 가능성이 큰 제목을 먼저, 화면 안내가 아닌 영상(탐방·브리핑·행사)은 뺌
STRONG = re.compile(r"신청하기|신청 방법|신청방법|따라하기|이용방법|이용 방법|조회|하는 법|온라인 신청|모바일|홈페이지|앱")
BAD = re.compile(r"탐방|태극기|브리핑|위클리|연휴|토크쇼|성과평가|행정심판|EP\d|인터뷰")


def ngrams(s, n=3):
    s = re.sub(r"\s+", "", s)
    return {s[i:i + n] for i in range(max(1, len(s) - n + 1))}


def jacc(a, b):
    A, B = ngrams(a), ngrams(b)
    return len(A & B) / max(1, len(A | B))


def select(a):
    cand = list(csv.DictReader(open(a.cand), delimiter="\t"))
    split = list(csv.DictReader(open(DOCS / "vlm_eval_split.tsv"), delimiter="\t"))
    excl = {r["youtube_id"] for r in csv.DictReader(open(DOCS / "vlm_eval_train_exclude.tsv"), delimiter="\t")}
    ev_ids = {r["youtube_id"] for r in split}; ev_ch = {r["channel_id"] for r in split}
    ev_titles = [r["title"] for r in split]
    ok, sus = [], []
    for r in cand:
        if r["youtube_id"] in ev_ids | excl or r["channel_id"] in ev_ch:
            continue
        if not (a.min_sec <= int(r["duration_sec"]) <= a.max_sec) or r["embeddable"] != "True":
            continue
        if BAD.search(r["title"]):
            continue
        sim = max(jacc(r["title"], t) for t in ev_titles)
        if sim >= 0.4:   # 재업로드·편집본 의심 → 제외하고 기록
            sus.append({**r, "max_title_sim": round(sim, 2)}); continue
        ok.append(r)
    # 채널마다 최대 2개, 정책이 겹치지 않게 돌아가며 고름 (최신 영상 우선: 화면이 지금 서비스와 비슷)
    by_ch = defaultdict(list)
    for r in sorted(ok, key=lambda r: r["published"], reverse=True):
        by_ch[r["channel"]].append(r)
    picked, seen_pol = [], defaultdict(int)
    for rnd in range(2):
        for ch in sorted(by_ch, key=lambda c: -len(by_ch[c])):
            rows = [r for r in by_ch[ch] if r not in picked]
            if not rows or len(picked) >= a.n:
                continue
            rows.sort(key=lambda r: (not STRONG.search(r["title"]), seen_pol[r["policy"].split("|")[0]]))
            picked.append(rows[0]); seen_pol[rows[0]["policy"].split("|")[0]] += 1
    assert not ({r["youtube_id"] for r in picked} & (ev_ids | excl)), "평가 영상이 학습 목록에 들어감"
    assert not ({r["channel_id"] for r in picked} & ev_ch), "평가 채널이 학습 목록에 들어감"
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(picked[0]), delimiter="\t"); w.writeheader(); w.writerows(picked)
    if sus:
        p = Path(a.out).with_name(Path(a.out).stem + "_suspect.tsv")
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(sus[0]), delimiter="\t"); w.writeheader(); w.writerows(sus)
        print(f"제목이 평가 영상과 비슷해 뺀 영상 {len(sus)}개 → {p}")
    print(f"학습 가능 {len(ok)}개 중 {len(picked)}개 선택 ({len({r['channel'] for r in picked})}개 채널, "
          f"{sum(int(r['duration_sec']) for r in picked) / 60:.0f}분) → {a.out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "select"])
    ap.add_argument("--out", required=True); ap.add_argument("--cand")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--min-sec", type=int, default=120); ap.add_argument("--max-sec", type=int, default=1200)
    a = ap.parse_args()
    if a.cmd == "collect":
        wc.CHANNELS, wc.POLICIES = CHANNELS, POLICIES
        sys.argv = [sys.argv[0], "--out", a.out, "--min-sec", str(a.min_sec), "--max-sec", str(a.max_sec)]
        wc.main()
    else:
        select(a)


if __name__ == "__main__":
    main()
