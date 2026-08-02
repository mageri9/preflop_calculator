from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.core.config import settings
from src.db.init_db import init_db
from src.db.seed_data import seed_tournament_data

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Keep every 2-9-max strategy dimension available after deploys."""
    init_db()
    seed_tournament_data()
    yield


app = FastAPI(title="Preflop Calculator", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/health")
async def health(): return {"status": "ok"}
