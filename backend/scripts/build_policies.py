"""시연용 정책 정보 만들기: 사회보장 공공데이터 두 API에서 받아 화면에 쓰는 일반 항목으로 정리 → backend/data/policies.json

- 한국사회보장정보원 중앙부처복지서비스(SSIS): 서비스 ID·명칭·요약·소관부처·지원대상·선정기준·지원내용·기준연도·문의처
- 행정안전부 공공서비스(혜택)(gov24): 지원대상·선정기준·지원내용·신청방법·신청기한·구비서류·문의처·온라인 신청 URL·수정일시
두 API가 같은 항목을 주면 gov24(신청 실무 항목이 더 자세함)를 먼저 쓰고, 없으면 SSIS. 항목마다 어느 API에서 왔는지 남긴다.
금액(amount)은 정책별로 사람이 고른 문구만 넣고, 그 문구가 공식 지원내용 원문에 그대로 있는지 확인한다(없으면 실패).

    python backend/scripts/build_policies.py            # API 호출 → backend/data/policies.json
"""
import json, re, sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/services"))
import welfare_api as w

OUT = ROOT / "backend/data/policies.json"

# 시연 정책 (2026-11-12, 중앙부처 서비스만). id는 두 API에서 서비스명으로 찾아 소관부처를 확인한 것.
POLICIES = [
    {"policyId": "basic-pension", "name": "기초연금", "category": "노후·연금", "ssis": "WLF00001164", "gov24": "SSE000000170",
     "keywords": ["기초연금", "노령연금", "65세", "어르신 연금"],
     "amount": [{"label": "혼자 사는 경우 최대(월)", "text": "349,700원"}, {"label": "부부 최대(월)", "text": "559,520원"}]},
    {"policyId": "child-care", "name": "아이돌봄서비스", "category": "돌봄·보육", "ssis": "WLF00000024", "gov24": "423000000362",
     "keywords": ["아이돌봄", "아이 돌봄", "돌보미", "육아 도우미", "맞벌이"], "amount": []},
    {"policyId": "youth-rent", "name": "청년월세 지원", "category": "주거", "ssis": "WLF00004661", "gov24": "161300000099",
     "keywords": ["청년월세", "청년 월세", "월세 지원", "청년 주거"], "amount": [{"label": "월 최대 (최대 24개월)", "text": "20만원"}]},
    {"policyId": "housing-benefit", "name": "주거급여(맞춤형 급여)", "category": "주거", "ssis": "WLF00003201", "gov24": "336000000096",
     "keywords": ["주거급여", "분리지급", "임차료", "청년 주거급여"], "amount": []},
]


def clean(s):
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("&divide;", "÷")
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def lines(s):
    out = []
    for l in clean(s).split("\n"):
        l = re.sub(r"^[\s○◦•\-·※*]+", "", l).strip()
        if l and l not in ("해당없음",):
            out.append(l)
    return out


def ssis(sid):
    root = w.ssis_detail(sid)
    return {e.tag: clean(e.text) for e in root.iter() if (e.text or "").strip() and len(list(e)) == 0}


def gov(sid):
    d = w.gov24("serviceDetail", **{"cond[서비스ID::EQ]": sid}).get("data", [])
    return {k: clean(v) if isinstance(v, str) else v for k, v in (d[0] if d else {}).items()}


def pick(g, gk, s, sk):
    if g.get(gk):
        return g[gk], "gov24"
    if s.get(sk):
        return s[sk], "ssis"
    return "", None


def build(p):
    s, g = ssis(p["ssis"]), gov(p["gov24"])
    fields, src = {}, {}
    for name, gk, sk in [("targetDetail", "지원대상", "tgtrDtlCn"), ("criteria", "선정기준", "slctCritCn"),
                         ("benefit", "지원내용", "alwServCn"), ("applyMethod", "신청방법", None),
                         ("applyWhen", "신청기한", None), ("contact", "문의처", "rprsCtadr")]:
        fields[name], src[name] = pick(g, gk, s, sk or "")
    fields["contact"] = fields["contact"].replace("||", " · ")
    docs = [{"id": f"{p['policyId']}-doc{i + 1}", "name": d} for i, d in enumerate(lines(g.get("구비서류")))]
    amounts = []
    for a in p["amount"]:
        whole = s.get("alwServCn", "") + "\n" + g.get("지원내용", "")
        assert a["text"] in whole, f"{p['name']}: 금액 문구 「{a['text']}」가 공식 지원내용에 없음"
        amounts.append({"label": a["label"], "value": a["text"], "source": "지원내용 원문"})
    return {
        "policyId": p["policyId"], "name": p["name"], "category": p["category"],
        "target": clean(s.get("wlfareInfoOutlCn") or g.get("서비스목적") or ""),
        **fields,
        "requiredDocs": docs,
        "agency": s.get("jurMnofNm") or g.get("소관기관명", ""),
        "applyUrl": g.get("온라인신청사이트URL") or f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={p['ssis']}",
        "officialUrls": [
            {"label": "복지로 서비스 안내", "url": f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={p['ssis']}"},
            {"label": "정부24 서비스 안내", "url": f"https://www.gov.kr/portal/rcvfvrSvc/dtlEx/{p['gov24']}"},
        ],
        "amount": amounts or None,
        "source": "한국사회보장정보원 복지서비스정보 · 행정안전부 공공서비스(혜택) 정보",
        "sourceIds": {"ssis": p["ssis"], "gov24": p["gov24"]},
        "fieldSource": src,
        "baseYear": int(s["crtrYr"]) if s.get("crtrYr", "").isdigit() else None,
        "updatedAt": g.get("수정일시") or "",
        "fetchedAt": date.today().isoformat(),
        "keywords": p["keywords"],
    }


def main():
    out = [build(p) for p in POLICIES]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in out:
        print(f"{p['name']}: 기준 {p['baseYear']}년, 수정 {p['updatedAt']}, 서류 {len(p['requiredDocs'])}개, 금액 {p['amount']}, 출처 {p['fieldSource']}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
