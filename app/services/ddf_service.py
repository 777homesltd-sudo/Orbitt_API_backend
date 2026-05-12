"""
AirRev Engine — DDF Service
Connects to CREA's Data Distribution Facility (DDF) OData API
Canadian REALTORS® feed — clean structured data, no scraping needed

Auth: OAuth 2.0 Client Credentials flow
  POST https://api.crea.ca/oauth2/token
    grant_type=client_credentials
    client_id=DDF_CLIENT_ID
    client_secret=DDF_CLIENT_SECRET
    scope=DDFApi_Read
  → Bearer token, expires in 3600s, cached for 50 minutes
"""

import time
import logging
from typing import Optional, Dict, Any

import httpx

from app.core.config import settings
from app.models.schemas import PropertyDetails

logger = logging.getLogger(__name__)


# ── Token cache (module-level, survives across requests) ──────────────────────
_token_cache: Dict[str, Any] = {
    "access_token": None,
    "expires_at": 0.0,  # Unix timestamp
}

TOKEN_CACHE_SECONDS = 50 * 60  # 50 minutes (token lives 60, refresh 10 early)


async def _get_access_token() -> str:
    """
    Return a valid Bearer token for the DDF API.
    Fetches a new one only when the cached token is expired or missing.
    """
    now = time.time()

    # Return cached token if still valid
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    logger.info("DDF token expired or missing — fetching new token from CREA OAuth endpoint")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            settings.DDF_TOKEN_ENDPOINT,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.DDF_CLIENT_ID,
                "client_secret": settings.DDF_CLIENT_SECRET,
                "scope": "DDFApi_Read",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            logger.error(
                f"DDF OAuth token request failed: {response.status_code} — {response.text}"
            )
            response.raise_for_status()

        data = response.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 3600)

        # Cache it
        _token_cache["access_token"] = token
        _token_cache["expires_at"] = now + min(expires_in, TOKEN_CACHE_SECONDS)

        logger.info(f"DDF token acquired — valid for {expires_in}s, cached for {TOKEN_CACHE_SECONDS}s")
        return token


class DDFService:
    """
    CREA DDF OData v1 client.
    Base URL: https://ddfapi.realtor.ca/odata/v1
    Auth: OAuth 2.0 Bearer token (auto-managed, cached 50 min)
    """

    BASE_URL = "https://ddfapi.realtor.ca/odata/v1"

    async def _headers(self) -> Dict[str, str]:
        """Build auth headers with a fresh (or cached) Bearer token."""
        token = await _get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "AirRev.io/1.0",
        }

    async def get_listing_by_mls(self, mls_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single listing by MLS® number from the DDF feed.

        DDF uses ListingId for the human-readable MLS number (e.g. A2123456).
        Falls back to ListingKey filter if not found by ListingId.
        Returns raw DDF JSON or None if not found.
        """
        headers = await self._headers()

        # Try ListingId first (the human-readable MLS® number shown on realtor.ca)
        for field in ("ListingId", "ListingKey"):
            filter_query = f"{field} eq '{mls_number}'"
            params = {
                "$filter": filter_query,
                "$top": 1,
                "$expand": "Media",
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                try:
                    response = await client.get(
                        f"{self.BASE_URL}/Property",
                        params=params,
                        headers=headers,
                    )

                    # If token expired mid-session (shouldn't happen with 50-min cache
                    # but handle it gracefully)
                    if response.status_code == 401:
                        logger.warning("DDF 401 — forcing token refresh and retrying")
                        _token_cache["expires_at"] = 0  # invalidate cache
                        headers = await self._headers()
                        response = await client.get(
                            f"{self.BASE_URL}/Property",
                            params=params,
                            headers=headers,
                        )

                    response.raise_for_status()
                    listings = response.json().get("value", [])

                    if listings:
                        logger.info(
                            f"DDF: found listing {mls_number} via {field} filter"
                        )
                        return listings[0]

                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"DDF API error fetching MLS {mls_number} "
                        f"({field}): {e.response.status_code}"
                    )
                    raise
                except httpx.RequestError as e:
                    logger.error(f"DDF connection error: {e}")
                    raise

        logger.warning(f"DDF: no listing found for MLS {mls_number}")
        return None

    async def search_listings_by_community(
        self,
        community: str,
        city: str = "Calgary",
        limit: int = 50,
    ) -> list:
        """
        Fetch active listings in a Calgary community for comp analysis.
        """
        headers = await self._headers()
        filter_query = (
            f"City eq '{city}' and CommunityName eq '{community}' "
            f"and StandardStatus eq 'Active'"
        )
        params = {
            "$filter": filter_query,
            "$top": limit,
            "$select": (
                "ListingKey,ListingId,ListPrice,BedroomsTotal,BathroomsTotalInteger,"
                "LivingArea,PropertyType,CommunityName,UnparsedAddress"
            ),
            "$orderby": "ListPrice asc",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/Property",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json().get("value", [])
            except Exception as e:
                logger.error(f"DDF community search error for {community}: {e}")
                return []

    def parse_property_details(self, raw: Dict[str, Any]) -> PropertyDetails:
        """
        Map raw DDF JSON fields → our PropertyDetails model.
        DDF field names follow RESO Data Dictionary standard.
        Uses ListingId as the MLS® number shown to users (e.g. A2123456).
        ListingKey is the internal DDF primary key (numeric string).
        """
        # Prefer the human-readable MLS number; fall back to ListingKey
        mls_number = raw.get("ListingId") or raw.get("ListingKey", "")

        # Build a realtor.ca URL from the ListingKey if available
        listing_key = raw.get("ListingKey", "")
        listing_url = (
            f"https://www.realtor.ca/real-estate/{listing_key}"
            if listing_key
            else None
        )

        return PropertyDetails(
            mls_number=mls_number,
            address=raw.get("UnparsedAddress", ""),
            community=raw.get("CommunityName", ""),
            city=raw.get("City", "Calgary"),
            province=raw.get("StateOrProvince", "AB"),
            postal_code=raw.get("PostalCode"),
            list_price=float(raw.get("ListPrice", 0)),
            bedrooms=int(raw.get("BedroomsTotal", 0)),
            bathrooms=float(raw.get("BathroomsTotalInteger", 0)),
            square_footage=float(raw["LivingArea"]) if raw.get("LivingArea") else None,
            property_type=raw.get("PropertyType", "Residential"),
            year_built=int(raw["YearBuilt"]) if raw.get("YearBuilt") else None,
            lot_size=float(raw["LotSizeArea"]) if raw.get("LotSizeArea") else None,
            parking=int(raw["ParkingTotal"]) if raw.get("ParkingTotal") else None,
            listing_url=listing_url,
            latitude=float(raw["Latitude"]) if raw.get("Latitude") else None,
            longitude=float(raw["Longitude"]) if raw.get("Longitude") else None,
        )


# Singleton
ddf_service = DDFService()
