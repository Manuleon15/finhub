"""Middleware de API key para auth del backend."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()

# Rutas que NO requieren API key
PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Verifica API key en header X-API-Key o query param api_key."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Permitir OPTIONS (CORS preflight) y rutas públicas
        if request.method == "OPTIONS" or path in PUBLIC_PATHS:
            return await call_next(request)

        # En dev, permitir sin key si es la key por defecto
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key", "")

        if api_key == settings.api_key:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "API key inválida o no proporcionada. Usa X-API-Key header."},
        )

