"""FastAPI entrypoint — FinHub backend."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import init_db
from app.core.security import APIKeyMiddleware
from app.modules.research.routes import router as research_router

logger = logging.getLogger("finhub")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: init DB."""
    logger.info("Inicializando base de datos...")
    init_db()
    logger.info("FinHub backend listo en http://localhost:8000")
    yield
    logger.info("FinHub backend apagado.")


app = FastAPI(
    title="FinHub API",
    version="0.1.0",
    description="Plataforma personal de análisis de inversiones. Núcleo 100% funcional sin IA.",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API key auth
app.add_middleware(APIKeyMiddleware)

# --- Routers ---
app.include_router(research_router, prefix="/api/research", tags=["Equity Research"])

# --- Health & root ---
@app.get("/")
def root():
    return {
        "name": "FinHub",
        "version": "0.1.0",
        "status": "running",
        "llm_enabled": settings.llm_enabled,
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/overview")
def overview():
    """Endpoint unificado: estado global."""
    return {
        "fx_usd_eur": settings.fx_usd_eur,
        "llm_enabled": settings.llm_enabled,
        "watchlist": settings.watchlist_list,
        "modules": ["research"],
    }

