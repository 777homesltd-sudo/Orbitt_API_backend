"""
AirRev.io Engine — Canadian Investment Property Analyzer
FastAPI Backend | DDF-powered | Supabase-logged | Railway-deployed
"""

import logging
import time
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import analyze, calculator, neighborhood, creb, reports
from app.core.config import settings
from app.core.cache import cache

# ── Logging setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("airrev")


# ── Lifespan (startup / shutdown) ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AirRev Engine starting up")
    logger.info(f"   Environment : {settings.APP_ENV}")
    logger.info(f"   AI enabled  : {settings.AI_ENABLED}")
    logger.info(f"   Supabase    : {'connected' if settings.SUPABASE_URL else 'not configured'}")
    logger.info(f"   DDF         : {'configured' if settings.DDF_CLIENT_ID else 'not configured'}")
    yield
    expired = cache.clear_expired()
    logger.info(f"🛑 AirRev Engine shutting down | cleared {expired} cache entries")


# ── App ──────────────────────────────────────────────────────
app = FastAPI(
    title="AirRev.io Engine",
    description=(
        "Canadian MLS Investment Property Analyzer\n\n"
        "Analyzes any MLS® listing for LTR and STR investment potential. "
        "Powered by CREA DDF. Built for Calgary, expandable across Canada."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000)
    if request.url.path not in ("/health", "/"):
        logger.info(
            f"{request.method} {request.url.path} "
            f"→ {response.status_code} ({duration_ms}ms)"
        )
    return response

# ── Global exception handler ──────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    # Surface real error in non-production so we can debug
    if settings.APP_ENV != "production":
        return JSONResponse(
            status_code=500,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
                "traceback": tb.splitlines()[-8:],
                "path": str(request.url.path),
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "Something went wrong. This has been logged.",
            "path": str(request.url.path),
        },
    )

# ── Routers ───────────────────────────────────────────────────
app.include_router(analyze.router,      prefix="/analyze",      tags=["Analysis"])
app.include_router(calculator.router,   prefix="/calculator",   tags=["Calculator"])
app.include_router(neighborhood.router, prefix="/neighborhood", tags=["Neighborhood"])
app.include_router(creb.router,         prefix="/creb",         tags=["CREB Reports"])
app.include_router(reports.router,      prefix="/reports",      tags=["Reports & PDF"])

# ── Debug endpoint (safe — shows only booleans, no secret values) ─────────────
@app.get("/debug/env", tags=["Health"], include_in_schema=False)
async def debug_env():
    """Confirm which env vars are actually set on Railway (values masked)."""
    return {
        "APP_ENV": settings.APP_ENV,
        "DDF_CLIENT_ID_set": bool(settings.DDF_CLIENT_ID),
        "DDF_CLIENT_SECRET_set": bool(settings.DDF_CLIENT_SECRET),
        "DDF_TOKEN_ENDPOINT": settings.DDF_TOKEN_ENDPOINT,
        "SUPABASE_URL_set": bool(settings.SUPABASE_URL),
        "SUPABASE_SERVICE_ROLE_KEY_set": bool(settings.SUPABASE_SERVICE_ROLE_KEY),
        "AIRREV_API_KEY_set": bool(settings.AIRREV_API_KEY and settings.AIRREV_API_KEY != "change-me-in-production"),
        "AIRROI_API_KEY_set": bool(settings.AIRROI_API_KEY),
    }


# ── Root endpoints ────────────────────────────────────────────
@app.get("/", tags=["Health"], include_in_schema=False)
async def root():
    return {
        "service": "AirRev.io Engine",
        "status": "online",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "analyze_listing":  "POST /analyze/listing",
            "quick_calc":       "POST /analyze/quick-calc",
            "investment_calc":  "POST /calculator/investment",
            "rent_insight":     "POST /calculator/rent-insight",
            "mortgage":         "GET  /calculator/mortgage-breakdown",
            "neighborhood":     "POST /neighborhood/insights",
            "communities":      "GET  /neighborhood/communities",
            "creb_report":      "GET  /creb/monthly-summary",
        },
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "cache_entries": cache.size,
        "environment": settings.APP_ENV,
    }


# ── Debug: test DDF token + first OData call ──────────────────
@app.get("/debug/ddf", tags=["Health"], include_in_schema=False)
async def debug_ddf():
    """Test the full DDF OAuth + OData flow and return raw responses."""
    import httpx
    results = {}

    # Step 1: token
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                settings.DDF_TOKEN_ENDPOINT,
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.DDF_CLIENT_ID,
                    "client_secret": settings.DDF_CLIENT_SECRET,
                    "scope": "DDFApi_Read",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            results["token_status"] = r.status_code
            if r.status_code == 200:
                token_data = r.json()
                token = token_data["access_token"]
                results["token_acquired"] = True
                results["expires_in"] = token_data.get("expires_in")

                # Step 2: test OData call
                r2 = await client.get(
                    f"{settings.DDF_API_URL}/Property",
                    params={"$filter": "ListingId eq 'A2294434'", "$top": 1},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
                results["odata_status"] = r2.status_code
                results["odata_response"] = r2.text[:1000]
            else:
                results["token_error"] = r.text[:500]
    except Exception as e:
        results["exception"] = str(e)

    return results
