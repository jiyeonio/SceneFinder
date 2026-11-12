"""복지바로봄 API (frontend/src/data/types.ts 모양).

  GET /api/welfare/search?q=&policy=   → SearchResponse (기본 결과 바로, n3_vlm이면 status 'pending' + jobId)
  GET /api/welfare/search/{jobId}      → 같은 모양, VLM 확인 뒤 순서·verification 갱신 (프론트가 폴링)
  GET /api/videos/{videoId}?jobId=&t=  → VideoDetail (policy·docs·officialSteps·chapters·subtitles)
  GET /api/welfare/health              → 방식·영상 수

검색 방식은 환경변수 SEARCH_MODEL (n3_vlm 기본 / n3). main 방식은 기존 /api/search 라우터를 씀.
"""
import json, os, threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

ROOT = Path(__file__).resolve().parents[2]
STEPS_DIR = ROOT / "backend/data/steps"
NOTICE = {
    "time_sensitive": "신청 기간·지금 신청 가능 여부는 영상에 나온 내용이 아니라 공식 정보로 확인해야 해요. 영상에는 해당 내용이 없어요, 공식 정보를 확인하세요.",
    "vlm_no_answer": "영상에는 해당 내용이 없어요, 공식 정보를 확인하세요.",
}
STEP_TITLES = {1: "지원 조건 확인", 2: "서류 준비", 3: "신청서 작성", 4: "결과 확인"}

_searcher = None
_lock = threading.Lock()


def searcher():
    global _searcher
    with _lock:
        if _searcher is None:
            from welfare_service import Searcher
            _searcher = Searcher(os.environ.get("SEARCH_MODEL", "n3_vlm"))
    return _searcher


def fmt(sec):
    sec = int(sec); return f"{sec // 60:02d}:{sec % 60:02d}"


def public_policy(p):
    keep = ["policyId", "name", "category", "target", "targetDetail", "criteria", "benefit", "applyMethod", "applyWhen", "contact",
            "agency", "applyUrl", "officialUrls", "amount", "source", "sourceIds", "baseYear", "updatedAt", "fetchedAt"]
    return {k: p.get(k) for k in keep} | {"requiredDocs": [d["name"] for d in p.get("requiredDocs", [])]}


def label_of(s, yid, span):
    t = s.ws.subtitle_text(yid, span, limit=60).strip()
    return t if t else "화면 장면"


def scene_results(s, out):
    cat = s.ws.catalog; res = []
    for v in out["videos"]:
        y = v["youtubeId"]; c = cat[y]; top = v["top"]; ver = v["verification"]
        res.append({
            "videoId": y, "youtubeVideoId": y, "title": c["title"], "publisher": c["channel"], "publishedAt": c["published"],
            "duration": fmt(c["duration_sec"]), "thumbnailUrl": f"https://i.ytimg.com/vi/{y}/hqdefault.jpg",
            "found": {"start": top[0][0], "end": top[0][1], "label": label_of(s, y, top[0]), "verification": ver[0]},
            "otherScenes": [{"start": sp[0], "end": sp[1], "label": label_of(s, y, sp), "verification": ver[i + 1] if i + 1 < len(ver) else "none"}
                            for i, sp in enumerate(top[1:3])],
        })
    return res


def response(s, out):
    from welfare_service import POLICIES
    pol = [public_policy(POLICIES[out["policyId"]])] if out["policyId"] else []
    return {"query": out["query"], "policies": pol, "scenes": scene_results(s, out), "jobId": out["jobId"], "status": out["status"],
            "official": out["official"], "notice": {"show": bool(out["noAnswerInVideo"]), "reason": out.get("noticeReason"),
                                                    "message": NOTICE.get(out.get("noticeReason") or "", "")},
            "model": s.mode, "timing": out["timing"]}


def steps_file(yid):
    f = STEPS_DIR / f"{yid}.json"
    return json.loads(f.read_text()) if f.exists() else None


def fill_gaps(chs, dur):
    """장면 사이 빈 곳을 「그 밖의 부분」으로 채워 영상 전체를 덮음 (지금 위치 찾기용)."""
    chs = sorted(chs, key=lambda c: c["start"]); out = []; t = 0.0; g = 0
    for c in chs:
        if c["start"] > t + 1:
            g += 1; out.append({"id": f"gap{g}", "start": t, "end": c["start"], "title": "그 밖의 부분", "short": "", "step": None,
                                "stepLabel": "", "verification": "none", "subtitle": "", "screenTitle": "", "relatedDocs": [], "gap": True})
        out.append(c); t = max(t, c["end"])
    if t < dur - 1:
        out.append({"id": f"gap{g + 1}", "start": t, "end": dur, "title": "그 밖의 부분", "short": "", "step": None, "stepLabel": "",
                    "verification": "none", "subtitle": "", "screenTitle": "", "relatedDocs": [], "gap": True})
    return out


def create_welfare_router() -> APIRouter:
    r = APIRouter()

    @r.get("/api/welfare/health")
    def health():
        s = searcher(); return {"model": s.mode, "videos": len(s.ws.catalog)}

    @r.get("/api/welfare/search")
    def search(q: str, policy: str | None = None):
        q = q.strip()
        if not q:
            raise HTTPException(400, "검색어가 비어 있어요")
        s = searcher(); out = s.start(q, policy)
        return response(s, out)

    @r.get("/api/welfare/search/{job_id}")
    def search_job(job_id: str):
        s = searcher(); out = s.job(job_id)
        if not out:
            raise HTTPException(404, "검색 결과가 만료됐어요. 다시 검색해 주세요")
        return response(s, out)

    @r.get("/api/videos/{video_id}")
    def video(video_id: str, jobId: str | None = None, t: float | None = None, e: float | None = None, policy: str | None = None):
        """찾은 장면 = 사용자가 누른 장면(t~e)이 항상 우선. 이 검색의 다른 장면, 단계 카드는 그와 겹치지 않을 때만 타임라인에 넣음
        (타임라인 장면이 서로 겹치지 않게). 오른쪽 공식 신청 단계는 단계 카드 파일에서 바로 만듦."""
        from welfare_service import POLICIES, POLICY_OF_HINT
        s = searcher(); cat = s.ws.catalog
        if video_id not in cat:
            raise HTTPException(404, "시연 영상 목록에 없는 영상이에요")
        c = cat[video_id]; dur = float(c["duration_sec"])
        job = s.job(jobId) if jobId else None
        pid = (job or {}).get("policyId") or policy or POLICY_OF_HINT.get(c["policy_hint"])
        p = POLICIES.get(pid)
        st = steps_file(video_id)
        v = next((x for x in (job or {}).get("videos", []) if x["youtubeId"] == video_id), None)
        tops = [(tuple(sp), (v["verification"][i] if v and i < len(v["verification"]) else "none")) for i, sp in enumerate((v or {}).get("top", [])[:3])]

        def scene(cid, sp, short, label, ver):
            return {"id": cid, "start": sp[0], "end": sp[1], "title": label_of(s, video_id, sp)[:40], "short": short, "step": None,
                    "stepLabel": label, "verification": ver, "subtitle": s.ws.subtitle_text(video_id, sp, 120), "screenTitle": "", "relatedDocs": []}

        cands = []   # 우선순위 순
        if t is not None:
            if e is None or e <= t:   # 끝을 모르면: 이 검색 결과 중 시작이 같은 장면, 없으면 그 시간의 자막 문장들
                hit = next((sp for sp, _ in tops if abs(sp[0] - t) < 0.6), None)
                if hit:
                    e = hit[1]
                else:
                    segs_ = s.ws.video(video_id)["segs"]
                    near = [x for x in segs_ if x["end_time"] > t and x["start_time"] < t + 12]
                    e = min(dur, max([x["end_time"] for x in near] + [t + 6]))
            ver = next((vv for sp, vv in tops if abs(sp[0] - t) < 0.6), "none")
            cands.append(scene("found1", (t, e), "찾은 장면" if job else "고른 장면", "찾은 장면" if job else "고른 장면", ver))
        for i, (sp, ver) in enumerate(tops):
            cands.append(scene(f"found{i + 1}" if t is None and i == 0 else f"other{i + 1}", sp,
                               "찾은 장면" if t is None and i == 0 else "다른 장면", "찾은 장면" if t is None and i == 0 else "다른 장면", ver))
        if st:
            cands += [dict(ch) for ch in sorted(st["chapters"], key=lambda x: x["step"] or 9)]
        chapters = []
        for ch in cands:   # 앞(우선) 장면과 겹치면 넣지 않음
            if all(min(ch["end"], k["end"]) - max(ch["start"], k["start"]) <= 0.5 for k in chapters):
                chapters.append(ch)
        chapters = fill_gaps(chapters, dur)
        matched = next((ch for ch in chapters if ch["id"] == "found1"), None) or next((ch for ch in chapters if not ch.get("gap")), chapters[0])
        steps_map = {ch["step"]: ch for ch in (st or {}).get("chapters", []) if ch.get("step")}
        official_steps = [{"step": k, "title": STEP_TITLES[k],
                           "note": {1: (p or {}).get("target", ""), 2: f"구비서류 {len((p or {}).get('requiredDocs', []))}가지",
                                    3: (p or {}).get("applyMethod", "")[:80], 4: f"문의 {(p or {}).get('contact', '')}"}[k],
                           **({"videoAt": steps_map[k]["start"]} if k in steps_map else {}),
                           "verification": steps_map[k]["verification"] if k in steps_map else "none"} for k in (1, 2, 3, 4)]
        segs = s.ws.video(video_id)["segs"]
        return {"videoId": video_id, "youtubeVideoId": video_id, "title": c["title"], "publisher": c["channel"], "publishedAt": c["published"],
                "durationSec": dur, "query": (job or {}).get("query", ""), "matchedChapterId": matched["id"], "chapters": chapters,
                "policy": public_policy(p) if p else None,
                "docs": [{"id": d["id"], "name": d["name"]} for d in (p or {}).get("requiredDocs", [])],
                "officialSteps": official_steps, "stepsStatus": (st or {}).get("status"),
                "subtitles": [{"start": x["start_time"], "end": x["end_time"], "text": x["text"].strip()} for x in segs]}

    return r
