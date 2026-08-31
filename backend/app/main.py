"""FastAPI entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth, cart, catalog, chat, profile
from app.clients import close_clients, init_clients
from app.config import get_settings
from app.observability import RequestContextMiddleware, configure_logging
from app.rate_limit import limiter

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_clients()
    if settings.uses_supabase:
        from app.bootstrap import ensure_schema, ensure_vector_collections
        from app.retrieval.catalog import load_catalog

        await ensure_schema()
        await ensure_vector_collections()
        catalog_items = await load_catalog()
        logger.info("startup: ready (%d products, env=%s)", len(catalog_items), settings.environment)
    yield
    await close_clients()


app = FastAPI(title="Smart Shopping Assistant", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(cart.router)
app.include_router(catalog.router)
app.include_router(auth.router)
app.include_router(profile.router)


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict:
    """Readiness probe: verifies the dependencies this service can't run without."""
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        from app.clients import qdrant_client

        await qdrant_client().get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"

    if settings.uses_supabase:
        try:
            from app.clients import supabase_client

            await supabase_client().table(settings.catalog_table).select("id").limit(1).execute()
            checks["supabase"] = "ok"
        except Exception as e:
            checks["supabase"] = f"error: {e}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ok" if healthy else "degraded", "checks": checks}
