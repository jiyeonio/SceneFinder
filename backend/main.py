from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Depends
from pydantic import BaseModel
from supabase import create_client
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import threading
import uuid

from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# DB/Storage 전용 클라이언트 (auth 작업에는 절대 사용하지 않음)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI()

_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = [
    o.strip()
    # 비어 있는 CORS_ORIGINS= 도 기본값을 쓰도록 `or` 사용
    for o in (os.getenv("CORS_ORIGINS") or _default_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== 인증 =====================

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str | None = None  # 선택. 표시용 이름

class LoginRequest(BaseModel):
    email: str
    password: str


def _user_name(user) -> str | None:
    meta = getattr(user, "user_metadata", None) or {}
    return meta.get("name")


@app.post("/api/auth/signup")
def signup(body: SignupRequest):
    auth_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    payload = {"email": body.email, "password": body.password}
    name = (body.name or "").strip()
    if name:
        payload["options"] = {"data": {"name": name}}
    try:
        result = auth_client.auth.sign_up(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "user_id": result.user.id if result.user else None,
        "email": result.user.email if result.user else None,
        "name": _user_name(result.user) if result.user else None,
    }

@app.post("/api/auth/login")
def login(body: LoginRequest):
    auth_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    try:
        result = auth_client.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")

    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
        "user_id": result.user.id,
        "email": result.user.email,
        "name": _user_name(result.user),
    }


# ===================== 공통: 토큰으로 현재 로그인한 유저 확인 =====================

def get_current_user(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    auth_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    try:
        user_response = auth_client.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    return user_response.user.id


# ===================== 기본 =====================

@app.get("/")
def root():
    return {"status": "ok"}


# ===================== 영상 =====================

@app.get("/api/videos")
def get_videos():
    response = supabase.table("videos").select("*").execute()
    return response.data

@app.post("/api/videos")
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    genre: str = Form(None),
):
    video_id = str(uuid.uuid4())
    ext = file.filename.split(".")[-1]
    storage_path = f"{video_id}.{ext}"

    file_bytes = await file.read()
    supabase.storage.from_("videos").upload(
        storage_path,
        file_bytes,
        {"content-type": file.content_type},
    )

    video_url = supabase.storage.from_("videos").get_public_url(storage_path)

    supabase.table("videos").insert({
        "video_id": video_id,
        "title": title,
        "video_url": video_url,
        "genre": genre,
        "status": "PENDING",
    }).execute()

    return {"video_id": video_id, "status": "PENDING", "video_url": video_url}


# ===================== 검색 기록 =====================

@app.get("/api/users/me/history")
def get_history(user_id: str = Depends(get_current_user)):
    response = (
        supabase.table("search_history")
        .select("*")
        .eq("user_id", user_id)
        .order("searched_at", desc=True)
        .execute()
    )
    return {"history": response.data}


# ===================== 즐겨찾기 =====================

class FavoriteRequest(BaseModel):
    # 둘 중 하나만 보내면 됩니다. (둘 다 보내면 video_id를 사용)
    video_id: str | None = None             # DB 내부 uuid
    youtube_video_id: str | None = None     # 유튜브 11자리 ID
    start_time: float
    end_time: float


def _video_brief(v: dict | None) -> dict | None:
    if not v:
        return None
    return {
        "video_id": v["video_id"],
        "youtube_video_id": v.get("youtube_video_id"),
        "title": v.get("title"),
        "channel_name": v.get("channel_name"),
        "thumbnail_url": v.get("thumbnail_url"),
    }


_VIDEO_BRIEF_COLUMNS = "video_id, youtube_video_id, title, channel_name, thumbnail_url"


@app.post("/api/users/me/favorites")
def add_favorite(body: FavoriteRequest, user_id: str = Depends(get_current_user)):
    if not body.video_id and not body.youtube_video_id:
        raise HTTPException(status_code=400, detail="video_id 또는 youtube_video_id가 필요합니다")

    query = supabase.table("videos").select(_VIDEO_BRIEF_COLUMNS)
    if body.video_id:
        query = query.eq("video_id", body.video_id)
    else:
        query = query.eq("youtube_video_id", body.youtube_video_id)
    found = query.limit(1).execute().data
    if not found:
        raise HTTPException(status_code=404, detail="등록되지 않은 영상입니다")
    video = found[0]

    response = supabase.table("favorites").insert({
        "user_id": user_id,
        "video_id": video["video_id"],
        "start_time": body.start_time,
        "end_time": body.end_time,
    }).execute()
    return {**response.data[0], "video": _video_brief(video)}

@app.delete("/api/users/me/favorites/{favorite_id}")
def delete_favorite(favorite_id: str, user_id: str = Depends(get_current_user)):
    supabase.table("favorites").delete().eq("favorite_id", favorite_id).eq("user_id", user_id).execute()
    return {"status": "deleted"}

@app.get("/api/users/me/favorites")
def get_favorites(user_id: str = Depends(get_current_user)):
    favorites = (
        supabase.table("favorites")
        .select("*")
        .eq("user_id", user_id)
        .execute()
        .data
    )

    # 영상 정보를 한 번에 가져와서 각 즐겨찾기에 붙입니다.
    video_ids = list({f["video_id"] for f in favorites if f.get("video_id")})
    videos = {}
    if video_ids:
        rows = (
            supabase.table("videos")
            .select(_VIDEO_BRIEF_COLUMNS)
            .in_("video_id", video_ids)
            .execute()
            .data
        )
        videos = {v["video_id"]: v for v in rows}

    favorites = [{**f, "video": _video_brief(videos.get(f.get("video_id")))} for f in favorites]
    favorites.sort(key=lambda f: f.get("created_at") or "", reverse=True)  # 최신순
    return {"favorites": favorites}


# ===================== 검색 (유튜브 / 분석 / 장면 검색) =====================

try:
    from .services.search_api import create_search_router, warmup_ai
except ImportError:
    from services.search_api import create_search_router, warmup_ai

app.include_router(create_search_router(get_current_user))


@app.on_event("startup")
def _warmup_on_startup():
    # 서버가 켜질 때 AI 모델을 미리 올려 첫 검색이 느려지지 않게 함
    threading.Thread(target=warmup_ai, daemon=True).start()