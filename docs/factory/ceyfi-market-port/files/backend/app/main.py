import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.services import metrics_store

from app.config import settings
from app.routers import mock, wallet, chat, tts, loans, business, payments, stt, auth, snapshot, banking_tools, market
from app.services.auth import (
    authorize_resource,
    is_public_path,
    match_path_resource,
    require_admin,
    requires_admin_path,
    resolve_session,
)
from payhere import router as payhere_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger(__name__)

telegram_app = None


# --- Simple in-memory rate limiter ---
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/chat": (20, 60),
    "/api/tts": (10, 60),
    "/api/stt": (10, 60),
    "/api/categorize-transactions": (5, 60),
    "/api/loans/advisor": (10, 60),
    "/api/payhere": (30, 60),
    "/api/payments": (30, 60),
}


def _check_rate_limit(path: str, client_ip: str) -> bool:
    for prefix, (max_requests, window_seconds) in _RATE_LIMITS.items():
        if path.startswith(prefix):
            key = f"{client_ip}:{prefix}"
            now = time.time()
            _rate_buckets[key] = [t for t in _rate_buckets[key] if now - t < window_seconds]
            if len(_rate_buckets[key]) >= max_requests:
                return False
            _rate_buckets[key].append(now)
            return True
    return True


async def _prewarm():
    """Pre-generate cached LLM responses so first page loads are instant."""
    if not settings.groq_api_key:
        log.info("PREWARM skipped — GROQ_API_KEY not set")
        return
    try:
        from app.routers.loans import _get_loans, _advisor_cache
        from app.services import groq_client
        from app.services.context_builder import build_loan_advisor_prompt
        for uid in ("SEY-USR-001", "SEY-USR-003"):
            cache_key = f"{uid}:primary"
            if cache_key not in _advisor_cache:
                loans = _get_loans(uid)
                if loans:
                    prompt = build_loan_advisor_prompt(loans[0])
                    text = await groq_client.complete(prompt, [{"role": "user", "content": "Give me my loan summary."}], max_tokens=256, temperature=0.3)
                    _advisor_cache[cache_key] = text
                    log.info("PREWARM advisor %s OK", uid)
    except Exception as exc:
        log.warning("PREWARM advisor failed: %s", exc)

    try:
        from app.services.categorizer import categorize_transactions
        import json
        from pathlib import Path
        fx = Path(__file__).parent.parent / "fixtures" / "business_account.json"
        data = json.loads(fx.read_text(encoding="utf-8"))
        txns = data.get("SEY-BIZ-001", {}).get("transactions", [])
        if txns:
            await categorize_transactions(txns)
            log.info("PREWARM categorization OK (%d txns)", len(txns))
    except Exception as exc:
        log.warning("PREWARM categorization failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app
    log.info("CEYFI API STARTING — legacy bank adapter enabled=%s", settings.use_seylan_real)
    if settings.database_url:
        from app.services import supabase_client
        asyncio.create_task(asyncio.to_thread(supabase_client.run_migrations))
    asyncio.create_task(_prewarm())

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        try:
            from telegram import Update  # noqa: PLC0415
            from telegram_bot.bot import build_application as build_telegram_app  # noqa: PLC0415
            telegram_app = build_telegram_app(token)
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            log.info("Telegram bot started")
        except Exception as exc:
            log.error("Telegram bot failed to start: %s", exc)
            telegram_app = None
    else:
        log.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")

    yield

    if telegram_app:
        try:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
            log.info("Telegram bot stopped")
        except Exception as exc:
            log.warning("Telegram bot shutdown error: %s", exc)
    log.info("shutdown")


app = FastAPI(title="CEYFI API", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def demo_auth_middleware(request: Request, call_next):
    """Require a valid demo session for protected API and mock routes."""
    path = request.url.path

    if request.method == "OPTIONS":
        return await call_next(request)

    if not settings.demo_auth_required:
        return await call_next(request)

    if is_public_path(path):
        return await call_next(request)

    if requires_admin_path(path):
        try:
            require_admin(request.headers.get("X-Demo-Admin-Key"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
        return await call_next(request)

    session = resolve_session(request.headers.get("Authorization"))
    if not session:
        return JSONResponse(status_code=401, content={"error": "Authentication required"})

    resource = match_path_resource(path)
    if resource:
        resource_type, resource_id = resource
        try:
            authorize_resource(session, resource_type, resource_id)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    request.state.session = session
    return await call_next(request)


@app.middleware("http")
async def body_size_limit_middleware(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_request_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request body too large"},
                )
        except ValueError:
            pass
    return await call_next(request)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    agent_key = metrics_store.route_to_agent(request.url.path)
    response = await call_next(request)
    if agent_key:
        latency_ms = (time.perf_counter() - t0) * 1000
        metrics_store.record(agent_key, latency_ms, response.status_code < 500)
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(request.url.path, client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Too many requests. Please try again later."},
            headers={"Retry-After": "60"},
        )

    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# Register CORS last so it wraps all custom middleware. Earlier registration
# leaves CORSMiddleware innermost, so auth 401/403 responses skip CORS headers
# and browsers report a misleading cross-origin error.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(snapshot.router)
app.include_router(mock.router)
app.include_router(wallet.router)
app.include_router(chat.router)
app.include_router(tts.router)
app.include_router(stt.router)
app.include_router(loans.router)
app.include_router(business.router)
app.include_router(payments.router)
app.include_router(payhere_router)


app.include_router(banking_tools.router)
app.include_router(market.router)


@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    log.error("unhandled error [%s] %s %s: %s", request_id, request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error", "request_id": request_id})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ceyfi-backend"}


@app.get("/health/ready")
async def health_ready():
    """ECS/Kubernetes readiness probe — verifies dependencies before accepting traffic."""
    checks: dict[str, str] = {}
    ready = True

    if settings.database_url:
        try:
            from app.services import supabase_client
            db_ok = supabase_client.ping()
            checks["database"] = "ok" if db_ok else "error"
            if not db_ok:
                ready = False
        except Exception:
            checks["database"] = "error"
            ready = False
    else:
        checks["database"] = "not_required"

    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ready else "not_ready", "checks": checks},
    )


@app.get("/api/metrics")
async def get_metrics():
    return metrics_store.get_all_metrics()


@app.get("/health/deep")
async def health_deep():
    deps: dict[str, str] = {}

    if settings.database_url:
        try:
            from app.services import supabase_client
            deps["database"] = "ok" if supabase_client.ping() else "error"
        except Exception:
            deps["database"] = "error"
    else:
        deps["database"] = "not_configured"

    deps["openai"] = "configured" if settings.openai_api_key else "not_configured"
    deps["groq"] = "configured" if settings.groq_api_key else "not_configured"
    deps["elevenlabs"] = "configured" if settings.elevenlabs_api_key else "not_configured"
    deps["seylan_real"] = "enabled" if settings.use_seylan_real else "disabled"
    deps["demo_auth"] = "enabled" if settings.demo_auth_required else "disabled"

    overall = "ok" if deps.get("groq") == "configured" or deps.get("openai") == "configured" else "degraded"
    return {"status": overall, "version": "0.2.0", "dependencies": deps}
