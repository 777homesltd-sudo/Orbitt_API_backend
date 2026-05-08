"""
AirRev Engine — AirROI Service
Talks to AirROI's API to fetch Airbnb comparable listings.
Used as the primary STR data source for /analyze/listing.
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class AirROIService:
    """
    AirROI API client. Fetches comparable Airbnb listings for a subject property.
    Pricing: ~$0.01-0.05 per call depending on endpoint.
    Documentation: https://www.airroi.com/api/documentation/
    """

    def __init__(self):
        self.base_url = settings.AIRROI_API_URL
        self.api_key = settings.AIRROI_API_KEY

    @property
    def enabled(self) -> bool:
        """True only when an API key is configured."""
        return bool(self.api_key)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def get_comparables(
        self,
        latitude: float,
        longitude: float,
        bedrooms: int,
        baths: float,
        guests: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch comparable Airbnb listings near a subject property.

        Returns a list of comp dicts in AirRev's normalized shape.
        Returns empty list (not an error) if AirROI is disabled or returns no comps.
        Raises HTTPException-friendly exceptions for real failures (rate limit, auth, etc.).
        """
        if not self.enabled:
            logger.warning("AirROI service disabled — no API key configured.")
            return []

        # Estimate guest capacity if not provided (industry rule of thumb: 2 guests per bedroom)
        if guests is None:
            guests = max(2, bedrooms * 2)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "bedrooms": bedrooms,
            "baths": baths,
            "guests": guests,
            "currency": "native",  # CAD for Calgary properties
        }

        url = f"{self.base_url}/listings/comparables"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                raw_listings = data.get("listings", [])
                logger.info(
                    f"AirROI returned {len(raw_listings)} comps for "
                    f"({latitude}, {longitude}) {bedrooms}bd/{baths}ba/{guests}g"
                )
                return [self._normalize_listing(listing) for listing in raw_listings]

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 403:
                logger.error("AirROI auth failed — check AIRROI_API_KEY.")
            elif status == 429:
                logger.error("AirROI rate limit hit.")
            elif status == 400:
                logger.error(f"AirROI bad request: {e.response.text}")
            else:
                logger.error(f"AirROI HTTP {status}: {e.response.text}")
            return []

        except Exception as e:
            logger.error(f"AirROI request failed: {e}")
            return []

    def _normalize_listing(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an AirROI listing into AirRev's internal comp shape.
        This is the contract between AirROI's response and the calculator service.
        """
        listing_info = listing.get("listing_info", {}) or {}
        location_info = listing.get("location_info", {}) or {}
        property_details = listing.get("property_details", {}) or {}
        booking_settings = listing.get("booking_settings", {}) or {}
        pricing_info = listing.get("pricing_info", {}) or {}
        ratings = listing.get("ratings", {}) or {}
        host_info = listing.get("host_info", {}) or {}
        metrics = listing.get("performance_metrics", {}) or {}

        return {
            # Identity
            "listing_id": listing_info.get("listing_id"),
            "listing_name": listing_info.get("listing_name"),
            "listing_url": (
                f"https://www.airbnb.com/rooms/{listing_info.get('listing_id')}"
                if listing_info.get("listing_id") else None
            ),
            "cover_photo_url": listing_info.get("cover_photo_url"),
            "room_type": listing_info.get("room_type"),
            "is_active_airbnb": True,  # By definition, AirROI only returns active listings

            # Location
            "latitude": location_info.get("latitude"),
            "longitude": location_info.get("longitude"),
            "district": location_info.get("district"),
            "locality": location_info.get("locality"),

            # Property
            "bedrooms": property_details.get("bedrooms"),
            "baths": property_details.get("baths"),
            "beds": property_details.get("beds"),
            "guests": property_details.get("guests"),
            "amenities": property_details.get("amenities", []),

            # Booking
            "min_nights": booking_settings.get("min_nights"),
            "instant_book": booking_settings.get("instant_book"),

            # Pricing
            "cleaning_fee": pricing_info.get("cleaning_fee"),
            "extra_guest_fee": pricing_info.get("extra_guest_fee"),

            # Reviews
            "num_reviews": ratings.get("num_reviews"),
            "rating_overall": ratings.get("rating_overall"),

            # Host
            "superhost": host_info.get("superhost", False),

            # Performance — AirRev's primary fields use trailing twelve months
            "annual_revenue": metrics.get("ttm_revenue"),
            "nightly_rate": metrics.get("ttm_avg_rate"),
            "occupancy_rate": metrics.get("ttm_adjusted_occupancy") or metrics.get("ttm_occupancy"),
            "revpar": metrics.get("ttm_adjusted_revpar") or metrics.get("ttm_revpar"),
            "days_reserved": metrics.get("ttm_days_reserved"),
            "available_days": metrics.get("ttm_available_days"),

            # Performance — last 90 days (more current signal)
            "l90d_revenue": metrics.get("l90d_revenue"),
            "l90d_avg_rate": metrics.get("l90d_avg_rate"),
            "l90d_occupancy": metrics.get("l90d_adjusted_occupancy") or metrics.get("l90d_occupancy"),
        }


# Singleton instance, used across the app
airroi = AirROIService()
