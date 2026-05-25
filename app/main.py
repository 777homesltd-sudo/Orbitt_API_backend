"""
AirRev.io Engine — Canadian Investment Property Analyzer
FastAPI Backend | DDF-powered | Supabase-logged | Railway-deployed
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import analyze, calculator, neighborhood, creb, reports, amenity_intelligence
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
    logger.info("AirRev Engine starting up")
    logger.info(f"   Environment : {settings.APP_ENV}")
    logger.info(f"   AI enabled  : {settings.AI_ENABLED}")
    logger.info(f"   Supabase    : {'connected' if settings.SUPABASE_URL else 'not configured'}")
    logger.info(f"   DDF         : {'configured' if settings.DDF_CLIENT_ID else 'not configured'}")
    yield
    expired = cache.clear_expired()
    logger.info(f"AirRev Engine shutting down | cleared {expired} cache entries")


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
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
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
app.include_router(amenity_intelligence.router)

# ── Root ─────────────────────────────────────────────────────
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
