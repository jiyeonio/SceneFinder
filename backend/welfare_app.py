"""복지바로봄 시연용 백엔드 (복지 검색·영상 API만, Supabase·기존 분석 라우터 없이).

    cd ~/scenefinder && set -a && . backend/.env && set +a
    HF_HUB_OFFLINE=1 HF_HOME=/nfs/team/data/huggingface SEARCH_MODEL=n3_vlm \
      .venv/bin/uvicorn backend.welfare_app:app --host 127.0.0.1 --port 8000

SEARCH_MODEL: n3_vlm(기본, VLM 재판별 포함) / n3. 첫 요청 전에 모델을 미리 올림(startup).
"""
import sys, threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend/services")]
from welfare_router import create_welfare_router, searcher  # noqa: E402

app = FastAPI(title="복지바로봄 API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])
app.include_router(create_welfare_router())


@app.on_event("startup")
def _load():
    threading.Thread(target=searcher, daemon=True).start()
