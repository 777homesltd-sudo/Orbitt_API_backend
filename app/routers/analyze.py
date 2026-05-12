"""
AirRev Engine — Analyze Listing Router
POST /analyze/listing  — The core AirRev Engine endpoint

Request flow:
1. Fetch property details from CREA DDF
2. Geocode if coordinates are missing
3. Check Supabase cache for nearby Airbnb comps (7-day freshness)
4. If stale or missing, fetch fresh comps from AirROI and cache them
5. Run mortgage math, LTR analysis, STR analysis using comp averages
6. Generate investment recommendation (Strong Buy / Buy / Hold / Avoid)
7. Return the full populated response
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.models.schemas import (
    AnalyzeListingRequest,
    AnalyzeListingResponse,
    AnalysisType,
)
from app.services.ddf_service import ddf_service
from app.services.calculator_service import calculator
from app.services.supabase_service import supabase
from app.services.airroi_service import airroi
from app.services.rent_service import rent_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _is_stale(last_scraped, days: int = 7) -> bool:
    """Check whether a cached comp is older than the freshness window."""
    if not last_scraped:
        return True
    if isinstance(last_scraped, str):
        try:
            scraped_time = datetime.fromisoformat(last_scraped.replace("Z", "+00:00"))
        except Exception:
            return True
    else:
        scraped_time = last_scraped
    if scraped_time.tzinfo is None:
        scraped_time = scraped_time.replace(tzinfo=timezone.utc)
    return scraped_time < datetime.now(timezone.utc) - timedelta(days=days)


def _avg(values: list) -> Optional[float]:
    """Average of a list, ignoring None/zero values. Returns None if empty."""
    valid = [v for v in values if v is not None and v > 0]
    return sum(valid) / len(valid) if valid else None


def _estimate_monthly_rent(
    community: str,
    bedrooms: int,
    property_type: str,
    square_footage: Optional[float],
    purchase_price: float,
) -> tuple[float, str]:
    """
    LTR rent estimate via rent_service community + bedroom lookup.
    Falls back to the 0.5% rule only if community is blank.
    Returns (monthly_rent, source_label).
    """
    if community:
        insight = rent_service.get_rent_estimate(
            community=community,
            bedrooms=bedrooms,
            property_type=property_type,
            square_footage=square_footage,
        )
        source = "community_benchmark" if community in insight.community else "calgary_default"
        return insight.avg_rent, source
    # Last resort: price-based rule
    return round(purchase_price * 0.005, 2), "price_rule_0.5pct"


@router.post("/listing", response_model=AnalyzeListingResponse)
async def analyze_listing(
    request: AnalyzeListingRequest,
    _: bool = Depends(require_api_key),
):
    # ──────────────────────────────────────
    # 1. PROPERTY DETAILS FROM DDF
    # ──────────────────────────────────────
    raw_listing = await ddf_service.get_listing_by_mls(request.mls_number)
    if not raw_listing:
        raise HTTPException(
            status_code=404,
            detail=(
                f"MLS® {request.mls_number} not found in DDF feed. "
                "Verify the listing is active and accessible via your DDF credentials."
            ),
        )
    property_details = ddf_service.parse_property_details(raw_listing)

    # User override for purchase price
    if request.purchase_price_override:
        property_details.list_price = request.purchase_price_override

    # ──────────────────────────────────────
    # 2. GEOCODE IF COORDINATES MISSING
    # ──────────────────────────────────────
    if not property_details.latitude or not property_details.longitude:
        try:
            from app.services.maps_service import maps_service
            address = (
                f"{getattr(property_details, 'address', '')}, "
                f"{getattr(property_details, 'city', '')}"
            )
            location = await maps_service.geocode(address)
            if location and "lat" in location and "lng" in location:
                property_details.latitude = location["lat"]
                property_details.longitude = location["lng"]
        except Exception as e:
            logger.warning(f"Geocoding failed for {property_details.mls_number}: {e}")

    # ──────────────────────────────────────
    # 3. AIRBNB COMP DATA — CACHE-FIRST, AIRROI-FALLBACK
    # ──────────────────────────────────────
    nearby_comps = []

    if property_details.latitude and property_details.longitude:
        # Layer 1: try the Supabase cache
        cached_comps = await supabase.get_nearby_airbnb_comps(
            lat=property_details.latitude,
            lng=property_details.longitude,
        )

        # Use cache only if fresh
        if cached_comps and not _is_stale(cached_comps[0].get("last_scraped")):
            nearby_comps = cached_comps
            logger.info(f"Using {len(nearby_comps)} cached comps.")
        else:
            # Layer 2: fetch fresh from AirROI
            logger.info("Cache miss or stale. Fetching from AirROI.")
            fresh_comps = await airroi.get_comparables(
                latitude=property_details.latitude,
                longitude=property_details.longitude,
                bedrooms=property_details.bedrooms,
                baths=property_details.bathrooms,
            )
            if fresh_comps:
                nearby_comps = fresh_comps
                # Save to cache (non-blocking failure)
                await supabase.save_airbnb_comps(fresh_comps)
            elif cached_comps:
                # AirROI failed but we have stale cache. Use it as a last resort.
                nearby_comps = cached_comps
                logger.info(f"AirROI returned no comps, falling back to {len(cached_comps)} stale cached comps.")

    # ──────────────────────────────────────
    # 4. MORTGAGE
    # ──────────────────────────────────────
    mortgage = calculator.calculate_mortgage(
        purchase_price=property_details.list_price,
        interest_rate=request.interest_rate,
        down_payment_pct=request.down_payment_pct,
        amortization_years=request.amortization_years,
    )

    # ──────────────────────────────────────
    # 5. LTR ANALYSIS
    # ──────────────────────────────────────
    if request.monthly_rent_override:
        monthly_rent = request.monthly_rent_override
        rent_source = "user_override"
    else:
        monthly_rent, rent_source = _estimate_monthly_rent(
            community=property_details.community or "",
            bedrooms=property_details.bedrooms or 2,
            property_type=property_details.property_type or "Apartment",
            square_footage=property_details.square_footage,
            purchase_price=property_details.list_price,
        )
    logger.info(f"LTR rent estimate: ${monthly_rent}/mo (source: {rent_source})")

    ltr_analysis = None
    if request.analysis_type in (AnalysisType.LTR, AnalysisType.BOTH):
        ltr_analysis = calculator.calculate_ltr(
            property=property_details,
            mortgage=mortgage,
            monthly_rent=monthly_rent,
        )

    # ──────────────────────────────────────
    # 6. STR ANALYSIS
    # ──────────────────────────────────────
    str_analysis = None
    if request.analysis_type in (AnalysisType.STR, AnalysisType.BOTH):
        # Derive subject property's projected rate and occupancy from comp averages
        comp_nightly_rates = [c.get("nightly_rate") for c in nearby_comps]
        comp_occupancies = [c.get("occupancy_rate") for c in nearby_comps]

        avg_rate = _avg(comp_nightly_rates)
        avg_occ = _avg(comp_occupancies)

        # Use override if provided, otherwise comp average, otherwise reasonable default
        nightly_rate = (
            request.nightly_rate_override
            if request.nightly_rate_override
            else (avg_rate if avg_rate else 200.0)
        )
        # Fall back to config default (1 - DEFAULT_VACANCY_RATE_STR = 0.70)
        from app.core.config import settings
        occupancy_rate = avg_occ if avg_occ else (1.0 - settings.DEFAULT_VACANCY_RATE_STR)

        str_analysis = calculator.calculate_str(
            property=property_details,
            mortgage=mortgage,
            nightly_rate=nightly_rate,
            occupancy_rate=occupancy_rate,
            nearby_airbnbs=nearby_comps,
            management_fee_pct=request.str_management_fee_pct,
            cleaning_pct=request.str_cleaning_pct,
        )

    # ──────────────────────────────────────
    # 7. INVESTMENT SUMMARY
    # ──────────────────────────────────────
    summary = calculator.generate_summary(
        ltr=ltr_analysis,
        str_analysis=str_analysis,
        analysis_type=request.analysis_type,
    )

    # ──────────────────────────────────────
    # 8. LOG ANALYTICS (non-blocking)
    # ──────────────────────────────────────
    report_id = await supabase.log_analysis(
        mls_number=property_details.mls_number,
        analysis_type=request.analysis_type.value,
        result_summary={
            "cap_rate_ltr": ltr_analysis.cap_rate if ltr_analysis else None,
            "cap_rate_str": str_analysis.cap_rate if str_analysis else None,
            "coc_ltr": ltr_analysis.cash_on_cash_return if ltr_analysis else None,
            "coc_str": str_analysis.cash_on_cash_return if str_analysis else None,
            "recommendation": summary.recommendation,
            "best_strategy": summary.best_strategy,
            "purchase_price": property_details.list_price,
            "community": property_details.community,
        },
    )

    # ──────────────────────────────────────
    # 9. RETURN FULL RESPONSE
    # ──────────────────────────────────────
    return AnalyzeListingResponse(
        property=property_details,
        mortgage=mortgage,
        ltr=ltr_analysis,
        str_analysis=str_analysis,
        summary=summary,
        report_id=report_id,
    )


@router.post("/quick-calc")
async def quick_calculate(
    purchase_price: float,
    monthly_rent: float,
    bedrooms: int = 2,
    _: bool = Depends(require_api_key),
):
    """
    Fast back-of-napkin calculation without MLS lookup.
    Useful for Lovable UI live sliders.
    """
    from app.models.schemas import PropertyDetails

    prop = PropertyDetails(
        mls_number="MANUAL",
        address="Manual Entry",
        community="Calgary",
        city="Calgary",
        province="AB",
        list_price=purchase_price,
        bedrooms=bedrooms,
        bathrooms=1.0,
        property_type="Residential",
    )

    mortgage = calculator.calculate_mortgage(purchase_price=purchase_price)
    ltr = calculator.calculate_ltr(prop, mortgage, monthly_rent)

    return {
        "purchase_price": purchase_price,
        "monthly_rent": monthly_rent,
        "mortgage_monthly": mortgage.monthly_payment,
        "cap_rate": ltr.cap_rate_display,
        "cash_on_cash": ltr.cash_on_cash_display,
        "monthly_cash_flow": ltr.monthly_cash_flow,
        "annual_cash_flow": ltr.annual_cash_flow,
        "noi": ltr.noi,
    }
