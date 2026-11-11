"""정답 없는 사용자 질문 판정용 공식 데이터 수집: 영상 정책별로 두 API에서 후보 서비스를 찾아 상세를 저장한다.

- 한국사회보장정보원_중앙부처복지서비스(목록 → 상세)
- 행정안전부_대한민국 공공서비스(혜택) 정보(serviceList → serviceDetail·supportConditions)

    python ai/experiments/vlm_model/fetch_official.py --keys dev01,dev03,dev04,dev05,dev08 \
        --out ai/experiments/vlm_model/results/official_dev.json
"""
import argparse, json, sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import welfare_api as w  # noqa: E402

# 영상 → 서비스 이름 검색어 (영상 제목·정책에서 정함, 결과를 보고 바꾸지 않음)
SEARCH = {
    "dev01": ["기초연금"], "dev02": ["국민연금"], "dev03": ["아이돌봄"], "dev04": ["청년월세", "청년 월세"],
    "dev05": ["구직급여", "실업급여"], "dev06": ["국민취업지원", "구직촉진수당"], "dev07": ["에너지바우처"],
    "dev08": ["요금감면", "통신요금", "이동통신"],
    "test01": ["기초연금"], "test02": ["아동수당"], "test03": ["아이돌봄"], "test04": ["청년월세", "청년 월세"],
    "test05": ["행복주택"], "test06": ["구직급여", "이직확인서"], "test07": ["장기요양"], "test08": ["근로장려금"],
}


def ssis(kw):
    out = []
    for it in w.ssis_list(kw, rows=20):
        root = w.ssis_detail(it["servId"])
        out.append({"api": "중앙부처복지서비스", "id": it["servId"], "name": it.get("servNm"),
                    "fields": {e.tag: e.text.strip() for e in root.iter() if (e.text or "").strip() and e.tag not in ("resultCode", "resultMessage")}})
    return out


def gov24(kw):
    out = []
    data = w.gov24("serviceList", perPage=30, **{"cond[서비스명::LIKE]": kw}).get("data", [])
    for it in data:
        sid = it["서비스ID"]
        det = w.gov24("serviceDetail", **{"cond[서비스ID::EQ]": sid}).get("data", [])
        out.append({"api": "공공서비스(혜택)정보", "id": sid, "name": it.get("서비스명"), "org": it.get("소관기관명"),
                    "fields": det[0] if det else it})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"fetched": date.today().isoformat(), "videos": {}}
    for k in a.keys.split(","):
        cands, seen = [], set()
        for kw in SEARCH[k]:
            for c in ssis(kw) + gov24(kw):
                if (c["api"], c["id"]) not in seen:
                    seen.add((c["api"], c["id"])); cands.append(c)
        res["videos"][k] = {"search": SEARCH[k], "candidates": cands}
        print(k, SEARCH[k], f"중앙부처 {sum(c['api'] == '중앙부처복지서비스' for c in cands)}건, 공공서비스 {sum(c['api'] != '중앙부처복지서비스' for c in cands)}건", flush=True)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
