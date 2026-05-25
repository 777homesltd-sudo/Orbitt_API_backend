import asyncio
import os
import httpx
from fastapi import APIRouter, BackgroundTasks
from supabase import create_client, Client
from datetime import datetime, timezone


router = APIRouter(prefix="/amenity-intelligence", tags=["Amenity Intelligence"])


AIRROI_BASE  = "https://api.airroi.com"
AIRROI_KEY   = os.getenv("AIRROI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


PAGE_SIZE  = 100
MIN_SAMPLE = 5


CALGARY = {
    "country":  "Canada",
    "region":   "Alberta",
    "locality": "Calgary"
}



def supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)



# ─────────────────────────────────────────────────────────────
# 1. FETCH ALL CALGARY LISTINGS FROM AIRROI
# ─────────────────────────────────────────────────────────────


async def fetch_all_listings(market: dict = CALGARY) -> list[dict]:
    """
    Pages through AirROI /listings/search until all entire-home
    Calgary listings with TTM revenue > 0 are collected.
    Returns a flat list with only the fields we need.
    """
    listings = []
    offset   = 0
    total    = None


    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            payload = {
                "market": market,
                "filter": {
                    "room_type":   {"eq": "entire_home"},
                    "ttm_revenue": {"gt": 0}
                },
                "pagination": {
                    "page_size": PAGE_SIZE,
                    "offset":    offset
                },
                "currency": "native"
            }


            resp = await client.post(
                f"{AIRROI_BASE}/listings/search",
                json=payload,
                headers={
                    "x-api-key":    AIRROI_KEY,
                    "Content-Type": "application/json"
                }
            )


            if resp.status_code != 200:
                raise RuntimeError(
                    f"AirROI {resp.status_code}: {resp.text[:300]}"
                )


            data       = resp.json()
            pagination = data.get("pagination", {})
            results    = data.get("results",    [])


            if total is None:
                total = pagination.get("total_count", 0)
                print(f"[AmenityIntel] Total Calgary listings: {total}")


            for r in results:
                prop  = r.get("property_details", {})
                perf  = r.get("performance_metrics", {})
                amens = prop.get("amenities") or []


                if not amens:
                    continue


                listings.append({
                    "amenities":              amens,
                    "ttm_revenue":            float(perf.get("ttm_revenue")            or 0),
                    "ttm_adjusted_occupancy": float(perf.get("ttm_adjusted_occupancy") or 0),
                    "ttm_avg_rate":           float(perf.get("ttm_avg_rate")           or 0),
                    "l90d_revenue":           float(perf.get("l90d_revenue")           or 0),
                    "cleaning_fee":           float(r.get("pricing_info", {}).get("cleaning_fee") or 0),
                })


            offset  += PAGE_SIZE
            fetched  = len(listings)
            print(f"[AmenityIntel] Fetched so far: {fetched} / {total}")


            if offset >= (total or 0) or not results:
                break


            await asyncio.sleep(0.4)  # respect rate limits


    return listings



# ─────────────────────────────────────────────────────────────
# 2. COMPUTE AMENITY INTELLIGENCE
# ─────────────────────────────────────────────────────────────


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0



def _quadrant(saturation_pct: float, rev_delta: float) -> str:
    high_sat = saturation_pct >= 50
    high_rev = rev_delta      >= 10000
    if not high_sat and high_rev:     return "gold_mine"
    if     high_sat and high_rev:     return "table_stakes"
    if not high_sat and not high_rev: return "niche"
    return "commodity"



def compute_intelligence(listings: list[dict], city: str = "Calgary") -> list[dict]:
    """
    For every unique amenity, compare listings that have it vs don't.
    Computes revenue delta, occupancy lift, ADR lift, and saturation.
    """
    total = len(listings)
    if total == 0:
        return []


    all_slugs: set[str] = set()
    for l in listings:
        all_slugs.update(l["amenities"])


    rows = []


    for slug in sorted(all_slugs):
        with_a    = [l for l in listings if slug     in l["amenities"]]
        without_a = [l for l in listings if slug not in l["amenities"]]


        if len(with_a) < MIN_SAMPLE or len(without_a) < MIN_SAMPLE:
            continue


        # Revenue
        avg_rev_with    = sum(l["ttm_revenue"] for l in with_a)    / len(with_a)
        avg_rev_without = sum(l["ttm_revenue"] for l in without_a) / len(without_a)
        rev_delta       = avg_rev_with - avg_rev_without


        # Adjusted occupancy
        avg_occ_with    = sum(l["ttm_adjusted_occupancy"] for l in with_a)    / len(with_a)
        avg_occ_without = sum(l["ttm_adjusted_occupancy"] for l in without_a) / len(without_a)
        occ_lift_pct    = _safe_div(avg_occ_with - avg_occ_without, avg_occ_without) * 100


        # ADR
        avg_adr_with    = sum(l["ttm_avg_rate"] for l in with_a)    / len(with_a)
        avg_adr_without = sum(l["ttm_avg_rate"] for l in without_a) / len(without_a)
        adr_lift_pct    = _safe_div(avg_adr_with - avg_adr_without, avg_adr_without) * 100


        # Saturation
        saturation_pct  = len(with_a) / total * 100


        rows.append({
            "city":                city,
            "country":             "Canada",
            "state":               "Alberta",
            "amenity_slug":        slug,
            "amenity_name":        slug.replace("_", " ").title(),
            "saturation_pct":      round(saturation_pct, 1),
            "listing_count_with":  len(with_a),
            "total_listings":      total,
            "rev_delta":           round(rev_delta,       2),
            "avg_rev_with":        round(avg_rev_with,    2),
            "avg_rev_without":     round(avg_rev_without, 2),
            "occ_lift_pct":        round(occ_lift_pct,    1),
            "avg_occ_with":        round(avg_occ_with    * 100, 1),
            "avg_occ_without":     round(avg_occ_without * 100, 1),
            "adr_lift_pct":        round(adr_lift_pct,    1),
            "avg_adr_with":        round(avg_adr_with,    2),
            "avg_adr_without":     round(avg_adr_without, 2),
            "opportunity_quadrant": _quadrant(saturation_pct, rev_delta),
            "last_updated":        datetime.now(timezone.utc).isoformat(),
        })


    rows.sort(key=lambda r: r["rev_delta"], reverse=True)
    return rows



# ─────────────────────────────────────────────────────────────
# 3. BACKGROUND JOB
# ─────────────────────────────────────────────────────────────


async def run_refresh_job(city: str = "Calgary"):
    print(f"[AmenityIntel] Starting refresh for {city}...")
    try:
        listings = await fetch_all_listings(CALGARY)
        print(f"[AmenityIntel] {len(listings)} listings with amenities")


        rows = compute_intelligence(listings, city)
        print(f"[AmenityIntel] {len(rows)} amenities computed")


        if not rows:
            print("[AmenityIntel] No rows — stopping")
            return


        sb = supabase()
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            sb.table("amenity_intelligence").upsert(
                batch, on_conflict="city,amenity_slug"
            ).execute()


        print(f"[AmenityIntel] Done. {len(rows)} rows upserted to Supabase.")


    except Exception as e:
        print(f"[AmenityIntel] ERROR: {e}")
        raise



# ─────────────────────────────────────────────────────────────
# 4. ENDPOINTS
# ─────────────────────────────────────────────────────────────


@router.post("/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """
    Kick off a fresh amenity intelligence computation.
    Runs in the background (~3-5 min for Calgary).
    Returns immediately.
    """
    background_tasks.add_task(run_refresh_job, "Calgary")
    return {
        "status":  "started",
        "message": "Refresh running in background. Check GET /amenity-intelligence in ~5 minutes."
    }



@router.get("")
async def get_amenity_intelligence(
    city:          str   = "Calgary",
    quadrant:      str   = None,
    min_rev_delta: float = 0,
    limit:         int   = 100
):
    """
    Returns cached amenity intelligence from Supabase, sorted by revenue delta.
    Filters: quadrant (gold_mine | table_stakes | niche | commodity),
             min_rev_delta, limit.
    """
    sb = supabase()
    q  = (
        sb.table("amenity_intelligence")
          .select("*")
          .eq("city", city)
          .gte("rev_delta", min_rev_delta)
          .order("rev_delta", desc=True)
          .limit(limit)
    )
    if quadrant:
        q = q.eq("opportunity_quadrant", quadrant)


    result = q.execute()
    data   = result.data or []


    return {
        "city":         city,
        "total":        len(data),
        "last_updated": max((r["last_updated"] for r in data), default=None),
        "amenities":    data
    }



@router.get("/gold-mine")
async def gold_mine(city: str = "Calgary"):
    """High impact, low saturation. The ones worth investing in."""
    return await get_amenity_intelligence(
        city=city, quadrant="gold_mine", min_rev_delta=5000, limit=30
    )



@router.get("/occupancy-drivers")
async def occupancy_drivers(city: str = "Calgary"):
    """Amenities that fill your calendar, sorted by occupancy lift."""
    sb     = supabase()
    result = (
        sb.table("amenity_intelligence")
          .select("*")
          .eq("city", city)
          .gte("occ_lift_pct", 10)
          .order("occ_lift_pct", desc=True)
          .limit(30)
          .execute()
    )
    data = result.data or []
    return {"city": city, "total": len(data), "amenities": data}



@router.get("/rate-drivers")
async def rate_drivers(city: str = "Calgary"):
    """Amenities that raise your nightly rate, sorted by ADR lift."""
    sb     = supabase()
    result = (
        sb.table("amenity_intelligence")
          .select("*")
          .eq("city", city)
          .gte("adr_lift_pct", 30)
          .order("adr_lift_pct", desc=True)
          .limit(30)
          .execute()
    )
    data = result.data or []
    return {"city": city, "total": len(data), "amenities": data}
