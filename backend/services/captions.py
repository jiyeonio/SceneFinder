"""VLM 설명문 검색: 설명문 생성(백그라운드, 대기열)·저장·검색 결합.

CAPTION_SEARCH_ENABLED=1일 때만 동작합니다. 꺼져 있으면 이 모듈의 함수는 아무것도 하지 않고,
검색·분석은 지금 서비스와 같은 경로로 갑니다. 설계: docs/design/vlm_search.md

저장 위치 (서버 디스크, git에 올라가지 않는 data/ 아래)
  data/processed/captions/{유튜브ID}.json      설명문과 창 정보
  data/processed/captions/{유튜브ID}.e5.pt     설명문 창 임베딩 (e5-large, float16)
  data/processed/subtitles/{유튜브ID}.minilm.pt 자막 창 임베딩 (fine-tuned MiniLM, float32, 자막 파일이 바뀌면 다시 계산)
상태는 DB의 video_captions 테이블에 기록합니다.
"""
import json
import logging
import math
import os
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("uvicorn.error")

ROOT = Path(__file__).resolve().parents[2]
CAPTION_DIR = ROOT / "data" / "processed" / "captions"
SUBTITLE_DIR = ROOT / "data" / "processed" / "subtitles"

CLIP_LEN = 2.0          # 2초마다 가운데 프레임 1장 (CLIP feature·실험과 같은 간격)
MAX_SIDE = 640          # 긴 변 640px로 줄여서 VLM에 넣음
MAX_NEW_TOKENS = 80
PROMPT = (
    "이 영상 장면을 보고 한국어 한 문장으로 설명하세요. 보이는 사람, 사물, 동작, 장소를 구체적으로 쓰고, "
    "화면에 글자나 자막이 있으면 그 내용도 함께 쓰세요. 설명 문장만 출력하세요."
)
# z-score를 쓰지 않는 조건 (2026-10-17, dev 비교 전에 정함. docs/design/vlm_search.md)
ZSCORE_MIN_WINDOWS = 5
ZSCORE_MIN_STD = 0.01
OVERLAP_DEDUPE = 0.5    # 결과 목록에서 겹침이 이 이상이면 같은 장면으로 보고 뺌 (search_api._dedupe와 같은 기준)


# ===================== 설정 (.env는 서버 시작 때 읽힘, 값은 부를 때마다 읽음) =====================

def enabled() -> bool:
    return os.getenv("CAPTION_SEARCH_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def _cfg():
    return {
        "model": os.getenv("CAPTION_MODEL", "Qwen/Qwen3-VL-4B-Instruct"),
        "batch_size": max(1, int(os.getenv("CAPTION_BATCH_SIZE", "8"))),
        "embed_model": os.getenv("CAPTION_EMBED_MODEL", "intfloat/multilingual-e5-large"),
        "fusion": os.getenv("CAPTION_FUSION", "zscore_max").strip(),
        "expand": float(os.getenv("CAPTION_SPAN_EXPAND_SEC", "2")),
        "idle_unload_min": float(os.getenv("CAPTION_IDLE_UNLOAD_MIN", "10")),
        "queue_max": max(0, int(os.getenv("CAPTION_QUEUE_MAX", "5"))),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===================== DB 상태 (video_captions) =====================

def _db():
    try:
        from . import indexer
    except ImportError:
        import indexer
    return indexer.supabase


def _set_status(video_id: str, status: str, **fields) -> None:
    row = {"video_id": video_id, "status": status, **fields}
    try:
        _db().table("video_captions").upsert(row, on_conflict="video_id").execute()
    except Exception as e:  # 상태 기록 실패가 분석·검색을 막지 않게 함
        logger.warning("[caption] 상태 기록 실패 %s %s: %s", video_id, status, e)


def get_status(video_id: str, youtube_video_id: str) -> str:
    """OFF(기능 꺼짐) / NONE(만든 적 없음) / PENDING / PROCESSING / READY / FAILED.
    DB가 READY여도 이 서버에 파일이 없거나 모델이 다르면 NONE."""
    if not enabled():
        return "OFF"
    try:
        rows = _db().table("video_captions").select("status").eq("video_id", video_id).limit(1).execute().data
    except Exception as e:
        logger.warning("[caption] 상태 조회 실패 %s: %s", video_id, e)
        return "NONE"
    if not rows:
        return "NONE"
    status = rows[0]["status"]
    if status == "READY" and load_index(youtube_video_id) is None:
        return "NONE"
    return status


def get_statuses(videos) -> dict:
    """여러 영상의 설명문 상태를 한 번에. videos: [(video_id, youtube_video_id)] → {video_id: 상태}"""
    if not enabled():
        return {vid: "OFF" for vid, _ in videos}
    ids = [vid for vid, _ in videos]
    try:
        rows = _db().table("video_captions").select("video_id,status").in_("video_id", ids).execute().data if ids else []
    except Exception as e:
        logger.warning("[caption] 상태 조회 실패: %s", e)
        rows = []
    db = {r["video_id"]: r["status"] for r in rows}
    out = {}
    for vid, yid in videos:
        st = db.get(vid, "NONE")
        out[vid] = "NONE" if st == "READY" and load_index(yid) is None else st
    return out


def cleanup_after_restart() -> None:
    """서버가 다시 켜졌을 때: 진행 중이던 작업은 FAILED, 대기 중이던 작업은 PENDING으로 안내만 남김."""
    if not enabled():
        return
    try:
        db = _db()
        db.table("video_captions").update({"status": "FAILED", "error_message": "서버 재시작으로 중단됨 (다시 분석하면 생성)"}) \
            .eq("status", "PROCESSING").execute()
        db.table("video_captions").update({"error_message": "서버 재시작으로 대기열에서 빠짐 (다시 분석하면 생성)"}) \
            .eq("status", "PENDING").is_("error_message", "null").execute()
    except Exception as e:
        logger.warning("[caption] 재시작 정리 실패: %s", e)


# ===================== 대기열 =====================

class _Ticket:
    def __init__(self, youtube_video_id: str, video_path: str, priority: bool, keep_file: bool, seq: int):
        self.youtube_video_id = youtube_video_id
        self.video_path = video_path
        self.priority = priority
        self.keep_file = keep_file   # 로컬 파일 분석이면 원본이라 디스크 사용량 집계에서 뺌
        self.seq = seq


class CaptionQueue:
    """동시에 1개만 생성. 대기는 최대 queue_max개, 우선(사용자 요청) 먼저, 같은 우선순위는 들어온 순서."""

    def __init__(self):
        self._cond = threading.Condition()
        self._waiting: list[_Ticket] = []
        self._running: _Ticket | None = None
        self._seq = 0

    def _sort(self):
        self._waiting.sort(key=lambda t: (not t.priority, t.seq))

    def _held_bytes(self) -> int:
        total = 0
        for t in self._waiting + ([self._running] if self._running else []):
            if not t.keep_file:
                try:
                    total += Path(t.video_path).stat().st_size
                except OSError:
                    pass
        return total

    def _log(self, event: str, t: _Ticket):
        logger.info("[caption] %s %s | 대기 %d개, 진행 %s | 설명문 때문에 남아 있는 영상 파일 %.1f MB",
                    event, t.youtube_video_id, len(self._waiting),
                    self._running.youtube_video_id if self._running else "없음", self._held_bytes() / 2**20)

    def try_enter(self, youtube_video_id: str, video_path: str, priority: bool, keep_file: bool, queue_max: int):
        with self._cond:
            if len(self._waiting) >= queue_max and (self._running is not None or self._waiting):
                return None
            self._seq += 1
            t = _Ticket(youtube_video_id, video_path, priority, keep_file, self._seq)
            self._waiting.append(t)
            self._sort()
            self._log("대기열 추가" + (" (우선)" if priority else ""), t)
            return t

    def wait_turn(self, t: _Ticket) -> None:
        with self._cond:
            while self._running is not None or self._waiting[0] is not t:
                self._cond.wait()
            self._waiting.pop(0)
            self._running = t
            self._log("생성 시작", t)

    def done(self, t: _Ticket) -> None:
        with self._cond:
            self._running = None
            self._log("생성 끝", t)
            self._cond.notify_all()

    def bump(self, youtube_video_id: str) -> bool:
        """대기 중인 영상을 맨 앞 우선순위로. 대기 중이면 True."""
        with self._cond:
            for t in self._waiting:
                if t.youtube_video_id == youtube_video_id:
                    if not t.priority:
                        t.priority = True
                        self._sort()
                        self._log("우선으로 옮김", t)
                        self._cond.notify_all()
                    return True
            return False

    def snapshot(self) -> dict:
        with self._cond:
            return {"running": self._running.youtube_video_id if self._running else None,
                    "waiting": [t.youtube_video_id for t in self._waiting], "held_mb": round(self._held_bytes() / 2**20, 1)}


QUEUE = CaptionQueue()


def bump(youtube_video_id: str) -> None:
    if enabled():
        QUEUE.bump(youtube_video_id)


# ===================== 프레임 =====================

def _duration(video_path: str) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def extract_frames(video_path: str, duration: float):
    """2초 구간마다 가운데(1, 3, 5, …초) 프레임 1장. ffmpeg 한 번으로 영상을 처음부터 읽으며 뽑습니다.
    (각 구간의 가운데 시각 이후 첫 프레임을 고르므로 시각이 밀리지 않음) 반환: [(시작, 끝, PIL 이미지)]"""
    from PIL import Image

    nbins = math.ceil(duration / CLIP_LEN)
    scale = f"scale='if(gt(iw,ih),{MAX_SIDE},-2)':'if(gt(iw,ih),-2,{MAX_SIDE})'"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video_path,
                        "-vf", f"select='gte(t\\,{CLIP_LEN / 2}+{CLIP_LEN}*selected_n)',{scale}",
                        "-fps_mode", "passthrough", "-q:v", "2", str(Path(tmp) / "%05d.jpg")], check=True)
        files = sorted(Path(tmp).glob("*.jpg"))[:nbins]
        frames = []
        for k in range(nbins):
            start, end = k * CLIP_LEN, min((k + 1) * CLIP_LEN, duration)
            if k < len(files):
                frames.append((start, end, Image.open(files[k]).convert("RGB")))
                continue
            # 마지막 구간이 짧아 한 번에 뽑지 못한 경우: 구간 가운데로 seek (실험과 같은 방식).
            # 영상 트랙이 오디오보다 짧으면 끝 근처에 프레임이 없어 조금씩 앞당기고, 그래도 없으면 직전 프레임을 씀
            mid = min((start + end) / 2, max(0.0, duration - 0.1))
            img = None
            for back in (0.0, 0.5, 1.0):
                path = Path(tmp) / f"last_{k}_{back}.jpg"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, mid - back):.3f}", "-i", video_path,
                                "-frames:v", "1", "-vf", scale, "-q:v", "2", str(path)], check=True)
                if path.exists():
                    img = Image.open(path).convert("RGB")
                    break
            if img is None and frames:
                img = frames[-1][2]
            if img is not None:
                frames.append((start, end, img))
    return frames


# ===================== 모델 =====================

class _Captioner:
    """Qwen3-VL. 필요할 때 올리고, CAPTION_IDLE_UNLOAD_MIN분 동안 안 쓰면 GPU에서 내림."""

    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._processor = None
        self._name = None
        self._last_used = 0.0
        self._timer = None

    def _load(self, name):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        t = time.perf_counter()
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(
            name, dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda").eval()
        self._processor = AutoProcessor.from_pretrained(name)
        self._processor.tokenizer.padding_side = "left"   # 묶음 생성 시 왼쪽 패딩
        self._name = name
        logger.info("[caption] %s 로딩 %.1f초", name, time.perf_counter() - t)

    def _unload_if_idle(self, idle_sec):
        with self._lock:
            if self._model is not None and time.time() - self._last_used >= idle_sec:
                import torch
                self._model = self._processor = None
                torch.cuda.empty_cache()
                logger.info("[caption] %.0f분 동안 쓰지 않아 설명문 모델을 GPU에서 내림", idle_sec / 60)

    def release(self) -> bool:
        """설명문을 만드는 중이 아니면 모델을 바로 내림. 내렸으면 True (만드는 중이면 기다리지 않고 False)."""
        if not self._lock.acquire(blocking=False):
            return False
        try:
            if self._model is None:
                return False
            import torch
            self._model = self._processor = None
            torch.cuda.empty_cache()
            logger.info("[caption] GPU 메모리가 부족해 설명문 모델을 내림 (다음 생성 때 다시 올림)")
            return True
        finally:
            self._lock.release()

    def caption(self, images, batch_size, name, idle_unload_min):
        import torch

        with self._lock:
            if self._model is None or self._name != name:
                self._model = None
                self._load(name)
            texts = []
            conv = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
            prompt = self._processor.apply_chat_template(conv, add_generation_prompt=True, tokenize=False)
            for i in range(0, len(images), batch_size):
                chunk = images[i:i + batch_size]
                inputs = self._processor(text=[prompt] * len(chunk), images=chunk, padding=True, return_tensors="pt").to("cuda")
                if "pixel_values" in inputs:
                    inputs["pixel_values"] = inputs["pixel_values"].to(torch.bfloat16)
                with torch.no_grad():
                    out = self._model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False)
                trimmed = out[:, inputs["input_ids"].shape[1]:]
                texts += [t.strip() for t in self._processor.batch_decode(trimmed, skip_special_tokens=True)]
                del inputs, out, trimmed
            # 묶음 생성에 쓴 캐시 메모리를 돌려줌. 안 하면 torch가 잡고 있어 Whisper(ctranslate2)가 GPU 메모리 부족으로 실패함
            torch.cuda.empty_cache()
            self._last_used = time.time()
        if idle_unload_min > 0:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(idle_unload_min * 60, self._unload_if_idle, args=(idle_unload_min * 60,))
            self._timer.daemon = True
            self._timer.start()
        return texts


_CAPTIONER = _Captioner()
_E5 = {"model": None, "name": None}
_E5_LOCK = threading.Lock()


def _e5(name):
    with _E5_LOCK:
        if _E5["model"] is None or _E5["name"] != name:
            import torch
            from sentence_transformers import SentenceTransformer
            _E5["model"] = SentenceTransformer(name, device="cuda" if torch.cuda.is_available() else "cpu")
            _E5["name"] = name
        return _E5["model"]


def _encode_e5(texts, name, prefix):
    model = _e5(name)
    with _E5_LOCK:
        return model.encode([prefix + t for t in texts], convert_to_tensor=True, normalize_embeddings=True, batch_size=64)


def release_gpu() -> bool:
    """다른 모델(Whisper)이 GPU 메모리가 부족할 때 부름. 설명문 모델을 내렸으면 True."""
    return _CAPTIONER.release()


def warmup() -> None:
    """기능이 켜져 있으면 검색에 쓰는 e5를 미리 올림 (설명문 모델은 생성할 때만)."""
    if enabled():
        _encode_e5(["워밍업"], _cfg()["embed_model"], "query: ")


# ===================== 창 (연속 1~3개) =====================

def windows(items):
    """자막·설명문 공통: 연속 1~3개를 묶은 창. fusion_search.get_semantic_subtitle_candidates와 같은 순서·텍스트."""
    out = []
    for size in (1, 2, 3):
        for i in range(len(items) - size + 1):
            g = items[i:i + size]
            out.append({"start_time": float(g[0]["start_time"]), "end_time": float(g[-1]["end_time"]),
                        "text": " ".join(s["text"] for s in g)})
    return out


# ===================== 생성 =====================

def _paths(youtube_video_id):
    return CAPTION_DIR / f"{youtube_video_id}.json", CAPTION_DIR / f"{youtube_video_id}.e5.pt"


def generate(video_id: str, youtube_video_id: str, video_path: str) -> int:
    """설명문 생성 → 창 임베딩 → 파일 저장. 프레임 수를 돌려줌."""
    import torch

    cfg = _cfg()
    duration = _duration(video_path)
    t = time.perf_counter()
    frames = extract_frames(video_path, duration)
    t_frames = time.perf_counter() - t
    t = time.perf_counter()
    texts = _CAPTIONER.caption([f[2] for f in frames], cfg["batch_size"], cfg["model"], cfg["idle_unload_min"])
    t_caption = time.perf_counter() - t
    caps = [{"start_time": s, "end_time": e, "text": x} for (s, e, _), x in zip(frames, texts)]
    wins = windows(caps)
    t = time.perf_counter()
    emb = _encode_e5([w["text"] for w in wins], cfg["embed_model"], "passage: ").half().cpu()
    t_embed = time.perf_counter() - t

    CAPTION_DIR.mkdir(parents=True, exist_ok=True)
    jpath, epath = _paths(youtube_video_id)
    meta = {"youtube_video_id": youtube_video_id, "duration": duration, "caption_model": cfg["model"], "prompt": PROMPT,
            "batch_size": cfg["batch_size"], "embed_model": cfg["embed_model"], "frames": len(caps), "created_at": _now(),
            "timing_sec": {"frames": round(t_frames, 1), "caption": round(t_caption, 1), "embed": round(t_embed, 1)}}
    tmp_e = epath.with_suffix(".tmp")
    torch.save(emb, tmp_e)
    tmp_e.replace(epath)
    jpath.write_text(json.dumps({"meta": meta, "captions": caps, "windows": wins}, ensure_ascii=False), encoding="utf-8")
    logger.info("[caption] %s 생성: %d장, 프레임 %.0f초 + 설명 %.0f초 + 임베딩 %.1f초",
                youtube_video_id, len(caps), t_frames, t_caption, t_embed)
    return len(caps)


def run_for_video(video_id: str, youtube_video_id: str, video_path: str, priority: bool = False, keep_file: bool = False) -> None:
    """run_indexing에서 INDEXED 다음에 부름. 차례를 기다려 생성하고 끝나면 돌아옴(그동안 영상 파일 유지).
    대기열이 가득 차면 PENDING만 기록하고 바로 돌아옴(영상 파일은 호출한 쪽이 평소처럼 지움)."""
    if not enabled():
        return
    cfg = _cfg()
    base = {"caption_model": cfg["model"], "embed_model": cfg["embed_model"], "batch_size": cfg["batch_size"]}
    ticket = QUEUE.try_enter(youtube_video_id, video_path, priority, keep_file, cfg["queue_max"])
    if ticket is None:
        _set_status(video_id, "PENDING", **base,
                    error_message=f"설명문 대기열이 가득 차(최대 {cfg['queue_max']}개) 만들지 않음. 다시 분석하면 생성")
        logger.info("[caption] 대기열이 가득 차 건너뜀 %s (PENDING)", youtube_video_id)
        return
    _set_status(video_id, "PENDING", **base, error_message=None, started_at=None, finished_at=None)
    QUEUE.wait_turn(ticket)
    try:
        _set_status(video_id, "PROCESSING", **base, error_message=None, started_at=_now())
        n = generate(video_id, youtube_video_id, video_path)
        _set_status(video_id, "READY", **base, num_frames=n, finished_at=_now(),
                    caption_path=_paths(youtube_video_id)[0].relative_to(ROOT).as_posix())
    except Exception as e:
        logger.warning("[caption] 생성 실패 %s: %s", youtube_video_id, e)
        _set_status(video_id, "FAILED", **base, error_message=str(e)[:500], finished_at=_now())
    finally:
        QUEUE.done(ticket)


# ===================== 검색 =====================

_INDEX_CACHE: dict = {}


def load_index(youtube_video_id: str):
    """설명문 파일과 임베딩. 없거나 지금 설정의 임베딩 모델과 다르면 None."""
    import torch

    jpath, epath = _paths(youtube_video_id)
    if not (jpath.exists() and epath.exists()):
        return None
    key = (youtube_video_id, jpath.stat().st_mtime, epath.stat().st_mtime)
    cached = _INDEX_CACHE.get(youtube_video_id)
    if cached and cached[0] == key:
        return cached[1]
    data = json.loads(jpath.read_text(encoding="utf-8"))
    if data["meta"].get("embed_model") != _cfg()["embed_model"]:
        return None
    data["emb"] = torch.load(epath, map_location="cpu")
    _INDEX_CACHE[youtube_video_id] = (key, data)
    return data


def _subtitle_embeddings(youtube_video_id, wins, model):
    """자막 창 임베딩을 파일로 저장해 다시 씀. 자막 파일이 바뀌면 다시 계산."""
    import torch

    sub_file = SUBTITLE_DIR / f"{youtube_video_id}.json"
    path = SUBTITLE_DIR / f"{youtube_video_id}.minilm.pt"
    stamp = [sub_file.stat().st_mtime, len(wins)] if sub_file.exists() else None
    if path.exists():
        try:
            saved = torch.load(path, map_location="cpu")
            if saved.get("stamp") == stamp:
                return saved["emb"].float()
        except Exception:
            pass
    # float32 그대로 저장: 지금 서비스(검색할 때마다 계산)와 점수·순위가 똑같게
    emb = model.encode([w["text"] for w in wins], convert_to_tensor=True).float().cpu()
    try:
        torch.save({"stamp": stamp, "emb": emb}, path)
    except OSError:
        pass
    return emb


def _zscores(scores):
    """(z-score 목록 또는 None). 창이 적거나 퍼짐이 매우 작으면 None."""
    n = len(scores)
    if n < ZSCORE_MIN_WINDOWS:
        return None
    mean = sum(scores) / n
    std = (sum((s - mean) ** 2 for s in scores) / n) ** 0.5
    if std < ZSCORE_MIN_STD:
        return None
    return [(s - mean) / std for s in scores]


def _overlap(a, b):
    inter = max(0.0, min(a["end_time"], b["end_time"]) - max(a["start_time"], b["start_time"]))
    shortest = min(a["end_time"] - a["start_time"], b["end_time"] - b["start_time"])
    return inter / shortest if shortest > 0 else 0.0


def fused_search(youtube_video_id: str, query: str, top_k: int, subtitles, index, widen, sub_model, ai_lock):
    """자막(있으면) + 설명문 결합. 결과는 [{start_time, end_time, score, source, rank_rule}] (점수는 각 모델의 코사인).
    widen: 자막 구간 보정 함수(search_api._widen_subtitle), sub_model: fine-tuned MiniLM, ai_lock: 자막 검색에 쓰는 잠금."""
    import torch
    from sentence_transformers import util

    cfg = _cfg()
    duration = float(index["meta"]["duration"])

    # 자막 쪽 (지금 서비스와 같은 창·점수, 임베딩만 저장본 사용)
    sub = []
    if subtitles:
        wins = windows(subtitles)
        with ai_lock:
            emb = _subtitle_embeddings(youtube_video_id, wins, sub_model)
            q = sub_model.encode(query, convert_to_tensor=True).float().cpu()
        scores = util.cos_sim(q, emb)[0].tolist()
        sub = [{**w, "score": s, "source": "subtitle"} for w, s in zip(wins, scores)]

    # 설명문 쪽
    qv = _encode_e5([query], cfg["embed_model"], "query: ")[0].float().cpu()
    cap_scores = (index["emb"].float() @ qv).tolist()
    cap = [{**w, "score": s, "source": "caption"} for w, s in zip(index["windows"], cap_scores)]

    # 1위 고르기
    rule = cfg["fusion"]
    z_sub = _zscores([m["score"] for m in sub]) if sub else None
    z_cap = _zscores([m["score"] for m in cap])
    if rule == "zscore_max" and sub and (z_sub is None or z_cap is None):
        rule = "subtitle_first(z불가)"
    for lst, z in ((sub, z_sub), (cap, z_cap)):
        for i, m in enumerate(lst):
            m["z"] = z[i] if z else None
    sub.sort(key=lambda m: -m["score"])
    cap.sort(key=lambda m: -m["score"])
    if not sub:
        first = "caption"
    elif rule == "zscore_max":
        first = "subtitle" if sub[0]["z"] >= cap[0]["z"] else "caption"
    else:
        first = "subtitle"

    # 구간: 자막은 서비스 보정, 설명문은 앞뒤 확장
    def span(m):
        if m["source"] == "subtitle":
            return widen([{"start_time": m["start_time"], "end_time": m["end_time"], "source": "subtitle"}])[0]
        s = max(0.0, m["start_time"] - cfg["expand"])
        e = min(duration, m["end_time"] + cfg["expand"])
        return {"start_time": round(s, 2), "end_time": round(e, 2)}

    order = [sub, cap] if first == "subtitle" else [cap, sub]
    merged, idx = [], [0, 0]
    while len(merged) < top_k and (idx[0] < len(order[0]) or idx[1] < len(order[1])):
        for j in (0, 1):
            while idx[j] < len(order[j]):
                m = order[j][idx[j]]
                idx[j] += 1
                cand = {**span(m), "score": round(float(m["score"]), 4), "source": m["source"], "rank_rule": rule}
                if all(_overlap(cand, k) < OVERLAP_DEDUPE for k in merged):
                    merged.append(cand)
                    break
            if len(merged) >= top_k:
                break
    return merged
