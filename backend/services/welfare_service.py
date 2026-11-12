"""복지바로봄 검색 조립: 정책 찾기 → 연결된 영상에서 장면 검색(N3) → (n3_vlm) VLM 재판별로 순서·verification 갱신 → 공식 정보 답.

- 정책 찾기: 질의에 정책 키워드가 있으면 그 정책, 없으면 요청의 policy(앞 화면 맥락), 둘 다 없으면 정책 없이 전체 영상
- 영상: 정책과 연결된 시연 영상(backend/data/demo_videos.json의 policy_hint → POLICY_OF_HINT). 정책이 없으면 전체.
- 영상 간 순서(검증 안 된 규칙): 기본 결과는 영상별 N3 1위의 자막 원점수(MiniLM 코사인) + 화면 원점수 순,
  VLM 확인 뒤에는 1위 장면의 P(답함) 순. 상위 MAX_VIDEOS개 영상만 VLM 확인.
- 공식 정보 답: 질문 의도(서류·기간·장소/방법·대상·금액)를 낱말로 나눠 정책 항목을 골라 보여줌.
- 「영상에 답 없음」 안내 (noAnswerInVideo, noticeReason):
  · time_sensitive: 신청 기간·지금 신청 가능 여부를 묻는 질문(의도 when)은 영상 장면과 관계없이 항상 안내.
    영상의 기간 안내는 게시 당시 기준이라, 제안서 원칙(신청 자격·기간은 최신 공식 정보를 근거로)대로 공식 정보로 답함.
  · vlm_no_answer: VLM 확인 뒤 보이는 장면의 P(답함)이 모두 0.5 미만(검증 안 된 규칙, dev에서 맞추지 않음).
"""
import json, re, threading, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICIES = {p["policyId"]: p for p in json.loads((ROOT / "backend/data/policies.json").read_text())}
POLICY_OF_HINT = {"기초연금": "basic-pension", "아이돌봄": "child-care", "청년주거": "youth-rent"}
MAX_VIDEOS = 3

INTENTS = [   # (의도, 정규식, 보여 줄 정책 항목)
    ("docs", r"서류|챙겨|준비물|가져가|내야|제출|필요한 거|뭐 내|뭘 내", ["requiredDocs"]),
    ("when", r"언제|기간|아직|마감|지금도|신청 되|신청돼|되는 거|접수", ["applyWhen", "updatedAt"]),
    ("where", r"어디|어떻게 신청|신청하는 법|신청 방법|신청방법|신청해요|신청하나요", ["applyMethod", "applyUrl"]),
    ("who", r"누가|대상|자격|받을 수|해당|조건", ["targetDetail", "criteria"]),
    ("amount", r"얼마|금액|받는 돈|지원금", ["amount", "benefit"]),
]


def match_policy(q, ctx=None):
    for pid, p in POLICIES.items():
        if any(k in q for k in p["keywords"]) or p["name"] in q:
            return pid
    return ctx if ctx in POLICIES else None


def intents(q):
    return [name for name, pat, _ in INTENTS if re.search(pat, q)]


def official_answer(pid, q):
    if not pid:
        return None
    p = POLICIES[pid]; out = []
    for name, pat, fields in INTENTS:
        if re.search(pat, q):
            for f in fields:
                if p.get(f):
                    out.append({"intent": name, "field": f, "value": p[f]})
    return {"policyId": pid, "items": out, "source": p["source"], "baseYear": p["baseYear"], "updatedAt": p["updatedAt"],
            "fetchedAt": p["fetchedAt"]}


class Searcher:
    """엔진(GPU)과 비동기 VLM 확인 작업을 관리."""

    def __init__(self, mode="n3_vlm"):
        from ai.features.welfare_search import WelfareSearch
        self.mode = mode
        self.ws = WelfareSearch(use_vlm=(mode == "n3_vlm"))
        self.jobs = {}
        self.queue_lock = threading.Lock()

    def videos_for(self, pid):
        cat = self.ws.catalog
        if pid:
            vids = [y for y, v in cat.items() if POLICY_OF_HINT.get(v["policy_hint"]) == pid]
            if vids:
                return vids
        return list(cat)

    def base(self, q, ctx=None):
        t0 = time.time()
        pid = match_policy(q, ctx)
        with self.ws.lock:
            mq, qv = self.ws.encode(q)
            res = {y: self.ws.n3(y, mq, qv) for y in self.videos_for(pid)}
        order = sorted(res, key=lambda y: -(res[y]["raw_sub"] + res[y]["raw_frame"]))
        out = {"query": q, "policyId": pid, "intents": intents(q), "official": official_answer(pid, q),
               "videos": [{"youtubeId": y, "top": res[y]["top"], "verification": ["pending"] * 3 if self.mode == "n3_vlm" else ["none"] * 3}
                          for y in order[:MAX_VIDEOS]],
               "otherVideos": order[MAX_VIDEOS:], "status": "pending" if self.mode == "n3_vlm" else "done",
               "noAnswerInVideo": True if "when" in intents(q) else None,
               "noticeReason": "time_sensitive" if "when" in intents(q) else None, "timing": {"base_sec": round(time.time() - t0, 3)}}
        return out

    def start(self, q, ctx=None):
        out = self.base(q, ctx)
        jid = uuid.uuid4().hex[:12]
        out["jobId"] = jid
        self.jobs[jid] = out
        if self.mode == "n3_vlm":
            threading.Thread(target=self._verify, args=(jid,), daemon=True).start()
        return out

    def _verify(self, jid):
        out = self.jobs[jid]; t0 = time.time()
        try:
            with self.ws.lock:
                for v in out["videos"]:
                    r = self.ws.rejudge(v["youtubeId"], out["query"], v["top"])
                    v.update(top=r["top"], verification=r["verification"], pAnswer=r["p_answer"], pScreen=r["p_screen"])
            out["videos"].sort(key=lambda v: -v["pAnswer"][0])
            if out["noticeReason"] != "time_sensitive":
                out["noAnswerInVideo"] = all(max(v["pAnswer"][:3]) < 0.5 for v in out["videos"])
                out["noticeReason"] = "vlm_no_answer" if out["noAnswerInVideo"] else None
            out["status"] = "done"
        except Exception as e:   # 확인 실패 시 기본 결과 그대로 두고 표시만
            out["status"] = "error"; out["error"] = str(e)[:200]
        out["timing"]["verify_sec"] = round(time.time() - t0, 3)

    def job(self, jid):
        return self.jobs.get(jid)
