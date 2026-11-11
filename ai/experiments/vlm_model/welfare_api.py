"""공공데이터포털 복지 API 호출 (키는 backend/.env의 DATA_GO_KR_KEY, 출력하지 않음).

- 한국사회보장정보원_중앙부처복지서비스 (XML): 목록 NationalWelfarelistV001, 상세 NationalWelfaredetailedV001
- 행정안전부_대한민국 공공서비스(혜택) 정보 (JSON, odcloud): serviceList, serviceDetail, supportConditions

    python ai/experiments/vlm_model/welfare_api.py test      # 두 API 시험 호출 (목록·상세 1건씩)
"""
import os, sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / "backend" / ".env")
KEY = os.getenv("DATA_GO_KR_KEY", "").strip()

SSIS = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
GOV24 = "https://api.odcloud.kr/api/gov24/v3"


class ApiError(RuntimeError):
    pass


def _redact(text):
    return str(text).replace(KEY, "***") if KEY else str(text)


def _get(url, params):
    try:
        r = requests.get(url, params={**params, "serviceKey": KEY}, timeout=30)
    except requests.RequestException as e:
        raise ApiError(_redact(e)) from None
    return r


def _xml_items(text):
    root = ET.fromstring(text)
    code = root.findtext(".//resultCode") or root.findtext(".//returnReasonCode")
    msg = root.findtext(".//resultMessage") or root.findtext(".//returnAuthMsg") or root.findtext(".//errMsg")
    return root, code, msg


def ssis_list(keyword, rows=10):
    """중앙부처복지서비스 목록 검색 (srchKeyCode 001 = 서비스명)."""
    r = _get(f"{SSIS}/NationalWelfarelistV001", {"callTp": "L", "pageNo": 1, "numOfRows": rows,
                                                  "srchKeyCode": "001", "searchWrd": keyword})
    if r.status_code != 200:
        raise ApiError(f"HTTP {r.status_code}: {_redact(r.text[:300])}")
    root, code, msg = _xml_items(r.text)
    if code not in (None, "0", "00", "000"):
        raise ApiError(f"결과 코드 {code}: {msg}")
    return [{c.tag: (c.text or "").strip() for c in item} for item in root.iter("servList")]


def ssis_detail(serv_id):
    r = _get(f"{SSIS}/NationalWelfaredetailedV001", {"callTp": "D", "servId": serv_id})
    if r.status_code != 200:
        raise ApiError(f"HTTP {r.status_code}: {_redact(r.text[:300])}")
    root, code, msg = _xml_items(r.text)
    if code not in (None, "0", "00", "000"):
        raise ApiError(f"결과 코드 {code}: {msg}")
    return root


def gov24(path, **params):
    r = _get(f"{GOV24}/{path}", {"page": 1, "perPage": 10, "returnType": "JSON", **params})
    if r.status_code != 200:
        raise ApiError(f"HTTP {r.status_code}: {_redact(r.text[:300])}")
    return r.json()


def test():
    if not KEY:
        sys.exit("DATA_GO_KR_KEY 없음")
    ok = True
    print("[1] 한국사회보장정보원_중앙부처복지서비스")
    try:
        items = ssis_list("기초연금")
        print(f"  목록: {len(items)}건  예) " + ", ".join(f"{i.get('servNm')}({i.get('servId')})" for i in items[:3]))
        if items:
            root = ssis_detail(items[0]["servId"])
            tags = sorted({e.tag for e in root.iter() if (e.text or "").strip()})
            print(f"  상세 {items[0]['servId']}: 항목 {len(tags)}개 예) {', '.join(tags[:12])}")
            print(f"    최종수정일 등: " + ", ".join(f"{t}={root.findtext('.//' + t)}" for t in ("lastModYmd", "crtrYr") if root.findtext(".//" + t)))
    except ApiError as e:
        ok = False; print(f"  실패: {e}")
    print("[2] 행정안전부_대한민국 공공서비스(혜택) 정보")
    try:
        j = gov24("serviceList", **{"cond[서비스명::LIKE]": "기초연금"})
        data = j.get("data", [])
        print(f"  목록: 전체 {j.get('totalCount')}건 중 {len(data)}건  예) " + ", ".join(f"{d.get('서비스명')}({d.get('서비스ID')})" for d in data[:3]))
        if data:
            sid = data[0]["서비스ID"]
            d = gov24("serviceDetail", **{"cond[서비스ID::EQ]": sid}).get("data", [])
            print(f"  상세 {sid}: 항목 {', '.join(list(d[0])[:12]) if d else '(없음)'}")
            c = gov24("supportConditions", **{"cond[서비스ID::EQ]": sid}).get("data", [])
            print(f"  지원조건 {sid}: {'항목 ' + str(len(c[0])) + '개' if c else '(없음)'}")
    except (ApiError, ValueError) as e:
        ok = False; print(f"  실패: {_redact(e)}")
    print("두 API 모두 정상" if ok else "실패한 API가 있음 (위 메시지 확인)")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test()
    else:
        print(__doc__)
