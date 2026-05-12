"""
AirRev Engine — Supabase Service
Logs searches, caches reports, stores community data, caches Airbnb comps
"""

import httpx
import logging
import math
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)

# Cache freshness: comps older than this trigger a fresh AirROI fetch
COMP_CACHE_DAYS = 7

# Search radius in kilometers for nearby comps
COMP_SEARCH_RADIUS_KM = 1.0


class SupabaseService:
    """
    Direct Supabase REST API client (no supabase-py dependency needed).
    Uses Service Key for server-side operations.
    """

    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.headers = {
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and settings.SUPABASE_SERVICE_ROLE_KEY)

    # ──────────────────────────────────────
    # ANALYTICS LOGGING (existing)
    # ──────────────────────────────────────

    async def log_analysis(
        self,
        mls_number: str,
        analysis_type: str,
        result_summary: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """Log a listing analysis to listing_analytics table."""
        if not self.enabled:
            return None

        payload = {
            "mls_number": mls_number,
            "analysis_type": analysis_type,
            "cap_rate_ltr": result_summary.get("cap_rate_ltr"),
            "cap_rate_str": result_summary.get("cap_rate_str"),
            "coc_ltr": result_summary.get("coc_ltr"),
            "coc_str": result_summary.get("coc_str"),
            "recommendation": result_summary.get("recommendation"),
            "best_strategy": result_summary.get("best_strategy"),
            "purchase_price": result_summary.get("purchase_price"),
            "community": result_summary.get("community"),
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/rest/v1/listing_analytics",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                return data[0].get("id") if data else None
            except Exception as e:
                logger.warning(f"Supabase log failed (non-critical): {e}")
                return None

    # ──────────────────────────────────────
    # COMMUNITY INSIGHTS (existing)
    # ──────────────────────────────────────

    async def get_community_insights(self, community: str) -> Optional[Dict[str, Any]]:
        """Fetch cached community insights from Supabase."""
        if not self.enabled:
            return None

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/rest/v1/community_insights",
                    params={
                        "community_name": f"eq.{community}",
                        "select": "*",
                        "limit": 1,
                    },
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                return data[0] if data else None
            except Exception as e:
                logger.warning(f"Supabase community fetch failed: {e}")
                return None

    # ──────────────────────────────────────
    # REPORT CACHE (existing)
    # ──────────────────────────────────────

    async def cache_report(
        self,
        mls_number: str,
        report_type: str,
        report_data: Dict[str, Any],
        ttl_hours: int = 24,
    ) -> Optional[str]:
        """Cache a report to avoid re-running expensive analysis."""
        if not self.enabled:
            return None

        payload = {
            "mls_number": mls_number,
            "report_type": report_type,
            "report_data": report_data,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": datetime.utcnow().isoformat(),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/rest/v1/report_cache",
                    json=payload,
                    headers={**self.headers, "Prefer": "resolution=merge-duplicates"},
                )
                response.raise_for_status()
                data = response.json()
                return data[0].get("id") if data else None
            except Exception as e:
                logger.warning(f"Supabase cache write failed: {e}")
                return None

    # ──────────────────────────────────────
    # AIRBNB COMP CACHE (new)
    # ──────────────────────────────────────

    async def get_nearby_airbnb_comps(
        self,
        lat: float,
        lng: float,
        radius_km: float = COMP_SEARCH_RADIUS_KM,
    ) -> List[Dict[str, Any]]:
        """
        Fetch cached Airbnb comps near a coordinate from Supabase.
        Filters by approximate radius using a lat/lng bounding box.
        Returns empty list if Supabase is disabled or returns nothing.
        """
        if not self.enabled:
            return []

        # Approximate degrees per km (good enough at Calgary's latitude)
        # 1 degree latitude ≈ 111 km
        # 1 degree longitude ≈ 111 km × cos(latitude)
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * max(0.01, abs(math.cos(math.radians(lat)))))

        lat_min = lat - lat_delta
        lat_max = lat + lat_delta
        lng_min = lng - lng_delta
        lng_max = lng + lng_delta

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/rest/v1/airbnb_listings",
                    params={
                        "select": "*",
                        "latitude": f"gte.{lat_min}",
                        "and": (
                            f"(latitude.lte.{lat_max},"
                            f"longitude.gte.{lng_min},"
                            f"longitude.lte.{lng_max})"
                        ),
                        "limit": 50,
                    },
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json() or []
                logger.info(f"Supabase cache hit: {len(data)} comps near ({lat}, {lng})")
                return data
            except Exception as e:
                logger.warning(f"Supabase comp fetch failed (non-critical): {e}")
                return []

    async def save_airbnb_comps(self, comps: List[Dict[str, Any]]) -> int:
        """
        Upsert Airbnb comps into the cache table.
        Returns the count saved. Failures are logged but don't crash the request.
        """
        if not self.enabled or not comps:
            return 0

        # Stamp each comp with the current scrape time
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = []
        for comp in comps:
            row = dict(comp)  # shallow copy so we don't mutate caller
            row["last_scraped"] = now_iso
            # Convert any list/dict fields to JSON if needed (Supabase handles this)
            rows.append(row)

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/rest/v1/airbnb_listings",
                    json=rows,
                    headers={
                        **self.headers,
                        "Prefer": "resolution=merge-duplicates,return=minimal",
                    },
                )
                response.raise_for_status()
                logger.info(f"Saved {len(rows)} Airbnb comps to Supabase cache.")
                return len(rows)
            except Exception as e:
                logger.warning(f"Supabase comp save failed (non-critical): {e}")
                return 0


# Singleton
supabase = SupabaseService()
