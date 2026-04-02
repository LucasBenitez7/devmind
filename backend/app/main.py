from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import DevMindException
from app.core.logger import setup_logging
from app.core.middleware import RequestIDMiddleware, devmind_exception_handler
from app.core.redis import close_redis, get_redis

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    log.info("devmind.startup", version=settings.version, environment=settings.environment)

    # Verify DB connection
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    log.info("devmind.db.connected")

    # Verify Redis connection
    redis = await get_redis()
    await redis.ping()
    log.info("devmind.redis.connected")

    yield

    await close_redis()
    await engine.dispose()
    log.info("devmind.shutdown")


app = FastAPI(
    title="DevMind",
    description="AI assistant for dev teams — RAG agent with internal docs + real-time web search",
    version=settings.version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middlewares
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(DevMindException, devmind_exception_handler)
app.add_exception_handler(Exception, devmind_exception_handler)


# Health endpoints
@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.version}


@app.get("/health/detailed", tags=["Health"])
async def health_detailed() -> dict[str, object]:
    import time

    from sqlalchemy import text

    db_start = time.perf_counter()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    db_latency = round((time.perf_counter() - db_start) * 1000)

    redis = await get_redis()
    redis_start = time.perf_counter()
    await redis.ping()
    redis_latency = round((time.perf_counter() - redis_start) * 1000)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        pgvector_active = result.scalar()

    return {
        "status": "ok",
        "db_latency_ms": db_latency,
        "redis_latency_ms": redis_latency,
        "pgvector_active": pgvector_active,
    }
