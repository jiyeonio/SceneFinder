import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

try:
    from .acquire import download_video
    from .subtitles import transcribe_video, load_subtitles
    from . import captions
except ImportError:
    from acquire import download_video
    from subtitles import transcribe_video, load_subtitles
    import captions

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
FEATURE_DIR = ROOT / "data" / "features"

load_dotenv(ROOT / "backend" / ".env")
USE_REAL_AI = os.getenv("USE_REAL_AI", "0").strip().lower() in ("1", "true", "yes", "on")
print("[indexer] USE_REAL_AI =", USE_REAL_AI, "(False면 가짜 결과로 동작합니다)")
MODEL_VERSION = "moment-detr-clip" if USE_REAL_AI else "stub"
_AI_LOCK = threading.Lock()  # GPU를 한 번에 하나만 쓰게 함

# ===================== 분석 실패 메시지 =====================
# 사용자에게는 한국어 안내만 보여주고, yt-dlp 등의 원문 오류는 서버 로그에만 남깁니다.
DOWNLOAD_BLOCKED_MESSAGE = "YouTube에서 일시적으로 영상 다운로드를 제한했어요. 잠시 후 다시 시도해주세요."
DOWNLOAD_UNAVAILABLE_MESSAGE = "영상을 다운로드할 수 없어요. 비공개이거나 삭제된 영상일 수 있어요."
ANALYSIS_ERROR_MESSAGE = "영상 분석 중 오류가 발생했어요. 잠시 후 다시 시도해주세요."

# 봇 확인, 403, 429 등: YouTube가 이 서버의 다운로드를 일시적으로 막은 경우
_BLOCKED_PATTERNS = (
    "confirm you", "not a bot", "http error 403", "http error 429",
    "too many requests", "rate-limit", "rate limit",
)
_UNAVAILABLE_PATTERNS = (
    "video unavailable", "private video", "this video is private",
    "has been removed", "account associated with this video has been terminated",
    "members-only", "this video is not available",
)
_HANGUL = ("가", "힣")


def user_error_message(raw: str | None) -> str | None:
    """원문 오류(영어 등)를 사용자용 한국어 안내로 바꿉니다. 이미 한국어면 그대로 둡니다."""
    if not raw:
        return raw
    low = raw.lower()
    if any(p in low for p in _BLOCKED_PATTERNS):
        return DOWNLOAD_BLOCKED_MESSAGE
    if any(p in low for p in _UNAVAILABLE_PATTERNS):
        return DOWNLOAD_UNAVAILABLE_MESSAGE
    if any(_HANGUL[0] <= ch <= _HANGUL[1] for ch in raw):
        return raw
    return ANALYSIS_ERROR_MESSAGE

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _retry(fn, tries: int = 3, delay: float = 0.6):
    """Supabase 연결이 잠깐 끊겼을 때(Server disconnected 등) 몇 번 다시 시도합니다."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            transient = any(k in type(e).__name__ + str(e) for k in
                            ("Disconnected", "RemoteProtocol", "ReadError", "ConnectError",
                             "Timeout", "ConnectionTerminated", "ReadTimeout"))
            if not transient or i == tries - 1:
                raise
            time.sleep(delay * (i + 1))


def _usable(feat) -> bool:
    """진짜 모드는 같은 모델 버전만, 가짜 모드는 이미 분석된 기록을 그대로 인정."""
    return bool(feat) and (not USE_REAL_AI or feat.get("model_version") == MODEL_VERSION)


def reclaim_stale(video_id: str, minutes: int = 30) -> bool:
    """서버가 꺼지는 바람에 멈춘 PROCESSING을 PENDING으로 되돌립니다."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    res = (
        supabase.table("videos")
        .update({"status": "PENDING", "error_message": None})
        .eq("video_id", video_id)
        .eq("status", "PROCESSING")
        .lt("updated_at", cutoff)
        .execute()
    )
    return bool(res.data)


def build_feature(video_path: str, video_id: str) -> str:
    if USE_REAL_AI:
        from ai.features.moment_detr_features import build_feature as real_build_feature
        with _AI_LOCK:
            return str(real_build_feature(video_path=video_path, video_id=video_id))
    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    out = FEATURE_DIR / f"{video_id}.stub"
    out.write_text(f"stub feature for {video_path}")
    return str(out)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_stored_path(p: str) -> str:
    """레포 안의 경로는 상대경로(슬래시)로 저장합니다."""
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def resolve_path(stored: str) -> Path:
    p = Path(stored)
    return p if p.is_absolute() else ROOT / p


def _feature_ready(feat) -> bool:
    """feature 기록이 쓸 수 있는 버전이고, 파일이 이 컴퓨터에 실제로 있는지 확인합니다.
    (DB는 팀원과 공유하지만 feature 파일은 각자 컴퓨터에 있기 때문입니다.)"""
    if not _usable(feat):
        return False
    return resolve_path(feat["feature_path"]).exists() if USE_REAL_AI else True



def _subtitle_ready(youtube_video_id: str) -> bool:
    """한국어 자막이 실제 검색 가능한 상태인지 확인합니다."""
    try:
        subtitles, language = load_subtitles(youtube_video_id)
        return language == "ko" and bool(subtitles)
    except Exception:
        return False


def get_video(youtube_video_id: str) -> dict | None:
    res = _retry(lambda: (
        supabase.table("videos")
        .select("*")
        .eq("youtube_video_id", youtube_video_id)
        .limit(1)
        .execute()
    ))
    return res.data[0] if res.data else None


def get_feature(video_id: str) -> dict | None:
    res = _retry(lambda: (
        supabase.table("video_features")
        .select("*")
        .eq("video_id", video_id)
        .order("id", desc=True)
        .limit(1)
        .execute()
    ))
    return res.data[0] if res.data else None


def register_video(youtube_video_id, title, channel_name=None,
                   published_at=None, thumbnail_url=None) -> dict:
    row = get_video(youtube_video_id)
    if row:
        return row
    try:
        res = supabase.table("videos").insert({
            "title": title,
            "youtube_video_id": youtube_video_id,
            "video_url": f"https://www.youtube.com/watch?v={youtube_video_id}",
            "thumbnail_url": thumbnail_url,
            "channel_name": channel_name,
            "published_at": published_at,
            "source_type": "youtube",
            "status": "PENDING",
        }).execute()
        return res.data[0]
    except Exception:
        # 동시에 같은 영상을 등록한 경우(중복 방지 인덱스)
        row = get_video(youtube_video_id)
        if row:
            return row
        raise


def set_status(video_id: str, status: str, error_message: str | None = None) -> None:
    supabase.table("videos").update(
        {"status": status, "error_message": error_message}
    ).eq("video_id", video_id).execute()


def claim(video_id: str) -> bool:
    """PENDING/FAILED일 때만 PROCESSING으로 바꿉니다. 성공한 한 요청만 분석을 시작합니다."""
    res = (
        supabase.table("videos")
        .update({"status": "PROCESSING", "error_message": None})
        .eq("video_id", video_id)
        .in_("status", ["PENDING", "FAILED"])
        .execute()
    )
    return bool(res.data)


def list_indexed(youtube_ids: list[str] | None = None, limit: int = 10) -> list[dict]:
    """분석 완료된 유튜브 영상 목록. 자막 또는 visual feature 중 하나만 있어도 사용 가능."""
    q = (
        supabase.table("videos")
        .select("*")
        .eq("status", "INDEXED")
        .eq("source_type", "youtube")
    )

    if youtube_ids:
        q = q.in_("youtube_video_id", youtube_ids)

    rows = _retry(lambda: q.order("last_used_at", desc=True).limit(limit).execute()).data
    if not rows:
        return []

    feats = _retry(lambda: (
        supabase.table("video_features")
        .select("video_id, feature_path, model_version, id")
        .in_("video_id", [r["video_id"] for r in rows])
        .order("id")
        .execute()
    )).data

    fmap = {
        f["video_id"]: f["feature_path"]
        for f in feats
        if _feature_ready(f)
    }

    result = []

    for row in rows:
        yid = row["youtube_video_id"]
        feature_path = fmap.get(row["video_id"])

        if _subtitle_ready(yid) or feature_path:
            result.append({
                **row,
                "feature_path": feature_path,
            })

    return result

def check_status(youtube_video_id: str) -> dict | None:
    row = get_video(youtube_video_id)
    if not row:
        return None
    if row["status"] == "PROCESSING" and reclaim_stale(row["video_id"]):
        row["status"] = "PENDING"
    feat = get_feature(row["video_id"])
    return {
        "youtube_video_id": youtube_video_id,
        "video_id": row["video_id"],
        "status": row["status"],
        "error_message": row.get("error_message"),
        "feature_path": feat["feature_path"] if feat else None,
    }


def prepare(youtube_video_id: str, title: str, force: bool = False, **meta) -> dict:
    """
    READY: 한국어 자막 또는 visual feature 중 하나가 검색 가능한 상태
    STARTED: 새 분석 시작 (force=True면 이미 분석된 영상도 다시 분석)
    PROCESSING: 이미 분석 중
    """
    row = register_video(youtube_video_id, title, **meta)
    vid = row["video_id"]
    feat = get_feature(vid)

    subtitle_ready = _subtitle_ready(youtube_video_id)
    feature_ready = _feature_ready(feat)

    if row["status"] == "INDEXED" and (subtitle_ready or feature_ready) and not force:
        supabase.table("videos").update({
            "last_used_at": _now()
        }).eq("video_id", vid).execute()

        return {
            "state": "READY",
            "video_id": vid,
            "feature_path": feat["feature_path"] if feature_ready else None,
        }

    if row["status"] == "PROCESSING":
        if not reclaim_stale(vid):
            return {
                "state": "PROCESSING",
                "video_id": vid
            }

    if row["status"] == "INDEXED":
        set_status(vid, "PENDING")

    if claim(vid):
        return {
            "state": "STARTED",
            "video_id": vid
        }

    return {
        "state": "PROCESSING",
        "video_id": vid
    }


def run_indexing(video_id: str, youtube_video_id: str, local_path: str | None = None, priority: bool = False) -> None:
    """
    다운로드 → Whisper 자막 생성 → 자막이 없을 때만 visual feature 생성 → 저장.
    Subtitle-first 구조에 맞춘 분석 파이프라인.

    local_path를 주면 YouTube에서 받지 않고 그 파일을 분석하며, 분석이 끝나도 파일을 지우지 않습니다.

    CAPTION_SEARCH_ENABLED=1이면 INDEXED(자막 검색 가능) 다음에 설명문 대기열에 넣고 바로 끝냅니다.
    설명문은 작업 스레드가 따로 만들고, 그 영상 파일도 작업 스레드가 생성 후 지웁니다
    (한 검색 요청의 여러 영상 분석이 차례로 실행되므로, 여기서 기다리면 다음 영상 분석이 늦어짐).
    priority=True면 설명문 대기열 맨 앞.
    """
    video_path = None
    file_handed_over = False   # 설명문 대기열이 영상 파일을 맡았으면 True (여기서 지우지 않음)

    try:
        total_start = time.perf_counter()

        if local_path:
            video_path = local_path
            print(f"[analysis] 로컬 파일 분석 {youtube_video_id}: {local_path}")
        else:
            t = time.perf_counter()
            video_path = download_video(
                youtube_video_id,
                out_dir=str(RAW_DIR)
            )
            print(
                f"[timing] download {youtube_video_id}: "
                f"{time.perf_counter() - t:.2f}s"
            )

        feature_path = None
        subtitles_available = False

        # 1) 자막을 먼저 생성
        if USE_REAL_AI:
            try:
                t = time.perf_counter()

                with _AI_LOCK:
                    transcribe_video(
                        str(video_path),
                        youtube_video_id
                    )

                print(
                    f"[timing] whisper {youtube_video_id}: "
                    f"{time.perf_counter() - t:.2f}s"
                )

                # 생성된 자막이 실제 검색 가능한지 확인
                try:
                    from .subtitles import load_subtitles
                except ImportError:
                    from subtitles import load_subtitles

                subtitles, language = load_subtitles(youtube_video_id)

                if language == "ko" and subtitles:
                    subtitles_available = True

            except Exception as e:
                print(
                    f"[subtitles] 자막 생성 실패 "
                    f"({youtube_video_id}): {e}"
                )

        # 2) 한국어 자막이 없을 때만 Moment-DETR feature 생성
        if not subtitles_available:
            t = time.perf_counter()

            feature_path = _to_stored_path(
                build_feature(
                    str(video_path),
                    youtube_video_id
                )
            )

            print(
                f"[timing] visual feature {youtube_video_id}: "
                f"{time.perf_counter() - t:.2f}s"
            )

            supabase.table("video_features").delete() \
                .eq("video_id", video_id).execute()

            supabase.table("video_features").insert({
                "video_id": video_id,
                "feature_path": feature_path,
                "model_version": MODEL_VERSION,
            }).execute()

        # 3) 분석 완료
        supabase.table("videos").update({
            "status": "INDEXED",
            "error_message": None,
            "last_used_at": _now(),
        }).eq("video_id", video_id).execute()

        print(
            f"[timing] TOTAL {youtube_video_id}: "
            f"{time.perf_counter() - total_start:.2f}s | "
            f"subtitle_ready={subtitles_available} | "
            f"visual_feature_generated={feature_path is not None}"
        )

        # 4) 설명문 (CAPTION_SEARCH_ENABLED=1일 때만). 자막 검색은 이미 가능하고, 여기서 실패해도 영상 상태는 그대로
        if USE_REAL_AI and captions.enabled():
            try:
                file_handed_over = captions.submit(video_id, youtube_video_id, str(video_path),
                                                   priority=priority, keep_file=bool(local_path))
            except Exception as e:
                print(f"[caption] 설명문 단계 오류 ({youtube_video_id}): {e}")

    except Exception as e:
        # 원문은 서버 로그에만, DB(사용자에게 보이는 값)에는 한국어 안내를 저장
        print(f"[analysis] FAILED {youtube_video_id}: {e}")
        set_status(
            video_id,
            "FAILED",
            user_error_message(str(e)[:500])
        )

    finally:
        # 내려받은 파일만 지움 (로컬 파일 분석이면 원본을 남김, 설명문 대기열이 맡았으면 작업 스레드가 지움)
        if not local_path and not file_handed_over and video_path and Path(video_path).exists():
            Path(video_path).unlink()

def backfill_subtitles(youtube_video_id: str) -> str:
    """이미 분석된 영상의 자막만 새로 만듭니다. (feature는 건드리지 않음)"""
    video_path = None
    try:
        video_path = download_video(youtube_video_id, out_dir=str(RAW_DIR))
        with _AI_LOCK:
            return transcribe_video(str(video_path), youtube_video_id)
    finally:
        if video_path and Path(video_path).exists():
            Path(video_path).unlink()


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "subs":
        print("자막 저장:", backfill_subtitles(sys.argv[2]))
        sys.exit(0)

    yid = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else yid
    r = prepare(yid, title)
    print("1차:", r)
    if r["state"] == "STARTED":
        run_indexing(r["video_id"], yid)
        print("상태:", check_status(yid))
    print("2차:", prepare(yid, title))