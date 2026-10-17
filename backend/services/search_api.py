import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from . import captions, indexer
    from .subtitles import load_subtitles
    from .translate import to_english
    from .youtube_search import fetch_video_meta, search_youtube_page
except ImportError:
    import captions
    import indexer
    from subtitles import load_subtitles
    from translate import to_english
    from youtube_search import fetch_video_meta, search_youtube_page

logger = logging.getLogger("uvicorn.error")

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_DURATION_SEC = 30 * 60  # 임시값. 팀 합의 후 조정
# 자막 구간은 말 한 문장 길이(1초 안팎)라 그대로는 장면을 보기 어렵습니다.
# 시작을 조금 앞당기고, 최소 길이를 보장합니다. (.env로 조정 가능)
SUBTITLE_PAD_BEFORE = float(os.getenv("SUBTITLE_PAD_BEFORE", "2.0"))
SUBTITLE_MIN_LEN = float(os.getenv("SUBTITLE_MIN_LEN", "6.0"))
PAGE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
MAX_MULTI_VIDEOS = 30  # /api/search/multi 한 번에 다룰 최대 영상 수
# YouTube가 다운로드를 막아 실패한 영상은 이 시간(분) 동안 다시 받지 않습니다. (.env로 조정, 0이면 끔)
DOWNLOAD_BLOCK_COOLDOWN_MIN = float(os.getenv("DOWNLOAD_BLOCK_COOLDOWN_MIN", "10"))
# 로컬 파일 분석: 서버 경로는 이 폴더들 안의 파일만 허용 (.env의 LOCAL_VIDEO_DIRS, 여러 개는 ':'로 구분)
LOCAL_VIDEO_DIRS = [Path(d).expanduser().resolve() for d in
                    os.getenv("LOCAL_VIDEO_DIRS", "~/scenefinder_eval/videos").split(os.pathsep) if d.strip()]
LOCAL_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
UPLOAD_DIR = indexer.ROOT / "data" / "uploads"   # 업로드한 영상을 두는 곳 (분석 후에도 지우지 않음)


def _video_duration(path: Path) -> float | None:
    """ffprobe로 영상 길이(초). 읽을 수 없으면 None."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _allowed_local_path(raw: str) -> Path | None:
    """허용된 폴더 안의 영상 파일이면 실제 경로, 아니면 None. (심볼릭 링크·..은 실제 경로로 바꿔 확인)"""
    p = Path(raw).expanduser().resolve()
    if p.suffix.lower() not in LOCAL_VIDEO_EXTS:
        return None
    if not any(p == d or d in p.parents for d in LOCAL_VIDEO_DIRS):
        return None
    return p


def _recently_blocked(row: dict | None) -> bool:
    """최근에 YouTube 다운로드 제한으로 실패한 영상인지 (재시도해도 같은 이유로 실패할 가능성이 높음)."""
    if not row or row.get("status") != "FAILED" or DOWNLOAD_BLOCK_COOLDOWN_MIN <= 0:
        return False
    if indexer.user_error_message(row.get("error_message")) != indexer.DOWNLOAD_BLOCKED_MESSAGE:
        return False
    try:
        failed_at = datetime.fromisoformat(row["updated_at"])
    except (KeyError, TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) - failed_at < timedelta(minutes=DOWNLOAD_BLOCK_COOLDOWN_MIN)

class SearchRequest(BaseModel):
    youtube_video_id: str
    query: str
    top_k: int = 5

class MultiSearchRequest(BaseModel):
    query: str
    youtube_video_ids: list[str] | None = None
    top_k_per_video: int = 3
    max_videos: int = 10
    auto_analyze: bool = False      # true면 미분석 영상의 분석을 백그라운드로 시작
    max_new_analyses: int = 3       # 한 번의 요청으로 새로 시작할 최대 영상 수 (최대 5)

def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status,
                        content={"error": {"code": code, "message": message}})


def _youtube_error(e: requests.HTTPError) -> JSONResponse:
    quota = e.response is not None and e.response.status_code == 403
    return _err(503 if quota else 502,
                "YOUTUBE_QUOTA" if quota else "YOUTUBE_ERROR",
                "유튜브 API 호출에 실패했습니다.")


def _score_of(r: dict) -> float:
    """영상 결과는 score, 자막 결과는 subtitle_score에 점수가 들어 있습니다."""
    s = r.get("score")
    if s is None:
        s = r.get("subtitle_score")
    return float(s) if s is not None else 0.0


def _overlap_ratio(a: dict, b: dict) -> float:
    """두 구간이 겹치는 정도 (겹치는 길이 / 더 짧은 구간 길이)."""
    inter = max(0.0, min(a["end_time"], b["end_time"]) - max(a["start_time"], b["start_time"]))
    shortest = min(a["end_time"] - a["start_time"], b["end_time"] - b["start_time"])
    return inter / shortest if shortest > 0 else 0.0


def _dedupe(moments: list[dict], top_k: int, threshold: float = 0.5) -> list[dict]:
    """점수 순서를 유지하면서, 이미 고른 구간과 많이 겹치는 구간은 건너뜁니다."""
    kept = []
    for m in moments:
        if all(_overlap_ratio(m, k) < threshold for k in kept):
            kept.append(m)
        if len(kept) == top_k:
            break
    return kept


def _widen_subtitle(moments: list[dict]) -> list[dict]:
    """자막(source=subtitle) 구간만 시작을 앞당기고 최소 길이를 보장합니다."""
    out = []
    for m in moments:
        if m.get("source") == "subtitle":
            start = max(0.0, m["start_time"] - SUBTITLE_PAD_BEFORE)
            end = max(m["end_time"], start + SUBTITLE_MIN_LEN)
            m = {**m, "start_time": round(start, 2), "end_time": round(end, 2)}
        out.append(m)
    return out


def _visual_search(video_id: str, feature_path: str, english_query: str, top_k: int):
    from ai.features.run_moment_detr_inference import predict_moments_hybrid

    return predict_moments_hybrid(
        video_id=video_id, video_feature_path=feature_path,
        query=english_query, top_k=top_k,
    )


def predict_moments(
    video_id: str,
    feature_path: str | None,
    query: str,
    top_k: int = 5
):
    """
    한국어 자막이 있으면 Fine-tuned MiniLM으로 바로 검색합니다.
    자막이 없을 때만 영어 번역 후 Moment-DETR visual fallback을 사용합니다.
    """
    if indexer.USE_REAL_AI:
        subtitles, language = load_subtitles(video_id)

        # 0) 설명문 검색이 켜져 있고 이 영상의 설명문이 준비됐으면 자막+설명문 결합 (docs/design/vlm_search.md)
        if captions.enabled():
            index = captions.load_index(video_id)
            if index is not None:
                try:
                    from ai.features.fusion_search import get_semantic_model
                    return captions.fused_search(
                        video_id, query, top_k,
                        subtitles if (language == "ko" and subtitles) else [],
                        index, _widen_subtitle, get_semantic_model(model_type="finetuned"), indexer._AI_LOCK)
                except Exception as e:
                    logger.warning("설명문 결합 검색 실패, 기존 검색으로 대신함: %s", e)

        # 1) 한국어 자막이 있으면 MiniLM 검색
        if language == "ko" and subtitles:
            from ai.features.fusion_search import predict_moments_fusion

            raw = None
            try:
                with indexer._AI_LOCK:
                    raw = predict_moments_fusion(
                        video_id=video_id,
                        feature_path=feature_path,
                        subtitles=subtitles,
                        korean_query=query,
                        english_query="",
                        video_duration=None,
                        top_k=top_k * 3,
                        model_type="finetuned",
                    )
            except Exception as e:
                # 모델 경로 설정 누락 등으로 자막 검색이 안 되면 영상 검색으로 대신합니다.
                logger.warning("자막 검색 실패: %s", e)

            if raw:
                moments = [
                    {
                        "start_time": r["start_time"],
                        "end_time": r["end_time"],
                        "score": _score_of(r),
                        "source": r.get("source"),
                    }
                    for r in raw
                ]
                return _dedupe(_widen_subtitle(moments), top_k)
            # 자막 결과가 없으면, 영상 feature가 있을 때만 아래 영상 검색으로 이어갑니다.

        # 2) 자막이 없을 때만 visual fallback
        if not feature_path:
            return []

        english_query = to_english(query)

        try:
            with indexer._AI_LOCK:
                raw = _visual_search(
                    video_id,
                    feature_path,
                    english_query,
                    top_k * 3,
                )
        except Exception as e:
            logger.warning("영상 검색 실패: %s", e)
            return []

        moments = [
            {
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "score": _score_of(r),
                "source": r.get("source"),
            }
            for r in raw
        ]

        return _dedupe(moments, top_k)

    return [
        {
            "start_time": 10.0 + 15 * i,
            "end_time": 20.0 + 15 * i,
            "score": round(0.9 - 0.1 * i, 2),
            "source": "stub",
        }
        for i in range(top_k)
    ]


def _try_start_analysis(yid: str, row: dict | None, background_tasks: BackgroundTasks):
    """미분석 영상의 분석을 시작합니다.
    반환: (새 상태 or None, 이번에 새로 시작했는지)
    None이면 상태를 바꾸지 않고 그대로 둡니다."""
    meta = {}
    if row is None:
        try:
            info = fetch_video_meta(yid)
        except requests.RequestException:
            return None, False
        if not info:
            return "NOT_FOUND", False
        if info["duration"] and info["duration"] > MAX_DURATION_SEC:
            return "TOO_LONG", False
        title = info["title"]
        meta = {"channel_name": info["channel_name"],
                "published_at": info["published_at"],
                "thumbnail_url": info["thumbnail_url"]}
    else:
        title = row["title"]

    r = indexer.prepare(yid, title, **meta)
    if r["state"] == "STARTED":
        background_tasks.add_task(indexer.run_indexing, r["video_id"], yid)
        return "PROCESSING", True
    if r["state"] == "PROCESSING":
        return "PROCESSING", False  # 이미 다른 요청이 분석 중
    return None, False  # READY: 방금 분석이 끝남. 다음 검색부터 결과에 나옴


def _moment(yid: str, i: int, m: dict) -> dict:
    return {"segment_id": f"{yid}-{i}", "start_time": m["start_time"],
            "end_time": m["end_time"], "score": m["score"],
            "source": m.get("source")}


def create_search_router(get_current_user) -> APIRouter:
    router = APIRouter()

    def optional_user(authorization: str | None = Header(None)):
        """로그인했으면 user_id, 아니면 None."""
        if not authorization:
            return None
        try:
            return get_current_user(authorization)
        except HTTPException:
            return None

    @router.get("/api/youtube/search")
    def youtube_search(q: str, max_results: int = 5, page_token: str | None = None):
        if not q.strip():
            return _err(400, "EMPTY_QUERY", "검색어가 비어 있습니다.")
        if page_token and not PAGE_TOKEN_RE.match(page_token):
            return _err(400, "INVALID_PAGE_TOKEN", "올바르지 않은 page_token입니다.")
        try:
            items, next_token = search_youtube_page(
                q.strip(), min(max(max_results, 1), 50), page_token or None
            )
        except requests.HTTPError as e:
            return _youtube_error(e)
        return {"items": items, "next_page_token": next_token}

    @router.get("/api/videos/youtube/{youtube_video_id}/status")
    def video_status(youtube_video_id: str):
        if not YOUTUBE_ID_RE.match(youtube_video_id):
            return _err(400, "INVALID_YOUTUBE_ID", "올바르지 않은 영상 ID입니다.")
        s = indexer.check_status(youtube_video_id)
        if not s:
            return _err(404, "VIDEO_NOT_FOUND", "등록되지 않은 영상입니다.")
        return {"youtube_video_id": youtube_video_id,
                "status": s["status"],
                "caption_status": captions.get_status(s["video_id"], youtube_video_id),
                # 예전에 저장된 영어 원문 오류도 한국어 안내로 바꿔서 전달
                "error_message": indexer.user_error_message(s["error_message"])}

    @router.post("/api/videos/youtube/{youtube_video_id}/analyze-local")
    def analyze_local(youtube_video_id: str, background_tasks: BackgroundTasks,
                      path: str | None = Form(None), file: UploadFile | None = File(None),
                      force: bool = Form(False)):
        """YouTube에서 받지 않고 서버의 영상 파일(path) 또는 업로드한 파일(file)로 분석합니다.
        분석 방식은 YouTube 영상과 같고(Whisper 자막, 필요하면 영상 feature), 분석 후 파일을 지우지 않습니다.
        검색은 기존처럼 youtube_video_id로 합니다."""
        yid = youtube_video_id.strip()
        if not YOUTUBE_ID_RE.match(yid):
            return _err(400, "INVALID_YOUTUBE_ID", "올바르지 않은 영상 ID입니다.")
        if (path is None) == (file is None):
            return _err(400, "LOCAL_SOURCE_REQUIRED", "path(서버 경로)와 file(업로드) 중 하나만 보내 주세요.")

        if path is not None:
            local = _allowed_local_path(path)
            if local is None:
                return _err(403, "LOCAL_PATH_NOT_ALLOWED",
                            "허용된 폴더(LOCAL_VIDEO_DIRS) 안의 영상 파일(mp4·mkv·webm·mov·m4v)만 분석할 수 있습니다.")
            if not local.is_file():
                return _err(404, "LOCAL_FILE_NOT_FOUND", "서버에 해당 영상 파일이 없습니다.")
        else:
            ext = Path(file.filename or "").suffix.lower()
            if ext not in LOCAL_VIDEO_EXTS:
                return _err(400, "UNSUPPORTED_FILE", "mp4·mkv·webm·mov·m4v 영상 파일만 올릴 수 있습니다.")
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            local = UPLOAD_DIR / f"{yid}{ext}"
            with local.open("wb") as f:
                shutil.copyfileobj(file.file, f)

        duration = _video_duration(local)
        if duration is None or duration > MAX_DURATION_SEC:
            if file is not None:
                local.unlink(missing_ok=True)   # 분석하지 않을 업로드 파일은 남기지 않음 (서버 경로 파일은 그대로)
            if duration is None:
                return _err(400, "INVALID_VIDEO_FILE", "영상 파일을 읽을 수 없습니다.")
            return _err(422, "VIDEO_TOO_LONG", f"{MAX_DURATION_SEC // 60}분 이하 영상만 분석할 수 있습니다.")

        row = indexer.get_video(yid)
        meta = {}
        if row is None:
            # 제목 등은 YouTube Data API로 가져옴 (영상 다운로드 아님). 없으면 파일 이름을 제목으로
            try:
                info = fetch_video_meta(yid)
            except requests.RequestException:
                info = None
            title = info["title"] if info else local.stem
            if info:
                meta = {"channel_name": info["channel_name"], "published_at": info["published_at"],
                        "thumbnail_url": info["thumbnail_url"]}
        else:
            title = row["title"]

        r = indexer.prepare(yid, title, force=force, **meta)
        if r["state"] == "STARTED":
            background_tasks.add_task(indexer.run_indexing, r["video_id"], yid, str(local), True)
            return JSONResponse(status_code=202, content={
                "status": "PROCESSING", "youtube_video_id": yid, "source": "local",
                "message": "로컬 영상 파일을 분석 중입니다.",
            })
        if r["state"] == "PROCESSING":
            return JSONResponse(status_code=202, content={
                "status": "PROCESSING", "youtube_video_id": yid,
                "message": "이미 분석 중인 영상입니다.",
            })
        return {"status": "INDEXED", "youtube_video_id": yid,
                "message": "이미 분석된 영상입니다. 다시 분석하려면 force=true로 보내 주세요."}

    @router.post("/api/search")
    def search(body: SearchRequest, background_tasks: BackgroundTasks,
               user_id=Depends(optional_user)):
        yid = body.youtube_video_id.strip()
        query = body.query.strip()
        top_k = min(max(body.top_k, 1), 10)

        if not YOUTUBE_ID_RE.match(yid):
            return _err(400, "INVALID_YOUTUBE_ID", "올바르지 않은 영상 ID입니다.")
        if not query:
            return _err(400, "EMPTY_QUERY", "검색어가 비어 있습니다.")

        row = indexer.get_video(yid)
        if _recently_blocked(row):
            # 다운로드가 막힌 직후에는 다시 받지 않음 (YouTube 요청을 줄여 제한이 더 길어지지 않게)
            logger.info("다운로드 제한 대기 중이라 재분석 생략: %s", yid)
            return _err(503, "DOWNLOAD_BLOCKED", indexer.DOWNLOAD_BLOCKED_MESSAGE)
        meta = {}
        if row is None:
            try:
                info = fetch_video_meta(yid)
            except requests.HTTPError as e:
                return _youtube_error(e)
            if not info:
                return _err(404, "VIDEO_NOT_FOUND", "유튜브에서 영상을 찾을 수 없습니다.")
            if info["duration"] and info["duration"] > MAX_DURATION_SEC:
                return _err(422, "VIDEO_TOO_LONG",
                            f"{MAX_DURATION_SEC // 60}분 이하 영상만 분석할 수 있습니다.")
            title = info["title"]
            meta = {"channel_name": info["channel_name"],
                    "published_at": info["published_at"],
                    "thumbnail_url": info["thumbnail_url"]}
        else:
            title = row["title"]

        r = indexer.prepare(yid, title, **meta)

        if r["state"] == "STARTED":
            # 사용자가 직접 연 영상이라 설명문 대기열 맨 앞
            background_tasks.add_task(indexer.run_indexing, r["video_id"], yid, None, True)
        if r["state"] in ("STARTED", "PROCESSING"):
            captions.bump(yid)
            return JSONResponse(status_code=202, content={
                "status": "PROCESSING",
                "youtube_video_id": yid,
                "caption_status": captions.get_status(r["video_id"], yid),
                "message": "영상을 분석 중입니다.",
            })
        captions.bump(yid)  # 설명문 대기 중이면 맨 앞으로

        feature_path = r.get("feature_path")
        feature = (
            str(indexer.resolve_path(feature_path))
            if feature_path
            else None
        )

        raw = predict_moments(
            yid,
            feature,
            query,
            top_k,
        )
        results = [_moment(yid, i, m) for i, m in enumerate(raw, start=1)]

        if user_id:
            try:
                indexer.supabase.table("search_history").insert(
                    {"user_id": user_id, "query": query}).execute()
            except Exception:
                pass  # 기록 저장 실패가 검색을 막지 않게 함

        v = indexer.get_video(yid)
        return {
            "status": "INDEXED",
            "caption_status": captions.get_status(v["video_id"], yid),
            "video": {"video_id": v["video_id"], "youtube_video_id": yid,
                      "title": v["title"], "thumbnail_url": v.get("thumbnail_url")},
            "query": query,
            "results": results,
        }

    @router.post("/api/search/multi")
    def search_multi(body: MultiSearchRequest, background_tasks: BackgroundTasks,
                     user_id=Depends(optional_user)):
        query = body.query.strip()
        if not query:
            return _err(400, "EMPTY_QUERY", "검색어가 비어 있습니다.")

        ids = None
        if body.youtube_video_ids:
            ids = [i.strip() for i in body.youtube_video_ids][:MAX_MULTI_VIDEOS]
            if not all(YOUTUBE_ID_RE.match(i) for i in ids):
                return _err(400, "INVALID_YOUTUBE_ID", "올바르지 않은 영상 ID가 있습니다.")

        top_k = min(max(body.top_k_per_video, 1), 5)
        limit = min(max(body.max_videos, 1), MAX_MULTI_VIDEOS)
        rows = indexer.list_indexed(ids, limit)

        videos = []
        for v in rows:
            yid = v["youtube_video_id"]
            try:
                feature_path = v.get("feature_path")
                feature = (
                    str(indexer.resolve_path(feature_path))
                    if feature_path
                    else None
                )

                raw = predict_moments(
                    yid,
                    feature,
                    query,
                    top_k,
                )
            except Exception:
                continue  # 한 영상이 실패해도 나머지는 계속
            moments = [_moment(yid, i, m) for i, m in enumerate(raw, start=1)]
            if not moments:
                continue
            videos.append({
                "video": {"video_id": v["video_id"], "youtube_video_id": yid,
                          "title": v["title"], "channel_name": v.get("channel_name"),
                          "thumbnail_url": v.get("thumbnail_url")},
                "best_score": max(m["score"] for m in moments),
                "moments": moments,
            })
        statuses = captions.get_statuses([(x["video"]["video_id"], x["video"]["youtube_video_id"]) for x in videos])
        for x in videos:
            x["caption_status"] = statuses.get(x["video"]["video_id"], "NONE")
        videos.sort(key=lambda x: x["best_score"], reverse=True)

        pending = []
        if ids:
            # 검색 가능한(자막 또는 feature가 있는) 영상은 결과가 0개여도 다시 분석하지 않음
            done = {v["youtube_video_id"] for v in rows}
            budget = min(max(body.max_new_analyses, 0), 5) if body.auto_analyze else 0
            for yid in ids:
                if yid in done:
                    continue
                row = indexer.get_video(yid)
                status = row["status"] if row else "NOT_ANALYZED"
                if status == "INDEXED":
                    status = "PENDING"  # 분석은 됐지만 이 컴퓨터에 feature 파일이 없어 다시 분석이 필요함
                # FAILED는 자동 재시도하지 않음 (사용자가 클릭하면 POST /api/search로 재시도)
                if budget > 0 and status in ("NOT_ANALYZED", "PENDING"):
                    new_status, started = _try_start_analysis(yid, row, background_tasks)
                    if new_status:
                        status = new_status
                    if started:
                        budget -= 1
                pending.append({"youtube_video_id": yid, "status": status})

        if user_id:
            try:
                indexer.supabase.table("search_history").insert(
                    {"user_id": user_id, "query": query}).execute()
            except Exception:
                pass

        return {"query": query, "videos": videos, "pending": pending}

    return router

def warmup_ai() -> None:
    """서버 시작 직후 모델을 미리 올려 첫 검색 지연을 없앱니다."""
    if not indexer.USE_REAL_AI:
        return
    if captions.enabled():
        try:
            captions.cleanup_after_restart()  # 이전 실행에서 멈춘 설명문 작업 정리
            captions.warmup()                 # 설명문 검색용 e5 미리 올리기
            logger.info("[caption] 설명문 검색 켜짐 (CAPTION_SEARCH_ENABLED=1)")
        except Exception as e:
            logger.warning("[caption] 준비 실패: %s", e)
    try:
        rows = indexer.list_indexed(limit=1)
        if rows:
            feature_path = rows[0].get("feature_path")
            feature = (
                str(indexer.resolve_path(feature_path))
                if feature_path
                else None
            )
            predict_moments(
                rows[0]["youtube_video_id"],
                feature,
                "warm up",
                1,
            )
    except Exception:
        pass
    try:
        with indexer._AI_LOCK:
            to_english("워밍업")  # 번역 모델 미리 올리기
            from ai.features.fusion_search import get_semantic_model
            get_semantic_model(model_type="finetuned")  # 한국어 MiniLM 미리 올리기
    except Exception as e:
        logger.warning("자막 검색/번역 모델 워밍업 실패: %s", e)