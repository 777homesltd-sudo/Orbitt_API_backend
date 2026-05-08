"""
AirRev Engine — Data Models
Request/Response schemas for all endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class AnalysisType(str, Enum):
    LTR = "ltr"      # Long-Term Rental
    STR = "str"      # Short-Term Rental / Airbnb
    BOTH = "both"    # Full comparison


# ─────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────

class AnalyzeListingRequest(BaseModel):
    mls_number: str = Field(..., description="MLS® listing number (e.g. A2123456)")
    analysis_type: AnalysisType = AnalysisType.BOTH

    # Optional overrides — user can tweak in the UI
    purchase_price_override: Optional[float] = None
    interest_rate: Optional[float] = None          # e.g. 0.059 for 5.9%
    down_payment_pct: Optional[float] = None       # e.g. 0.20 for 20%
    amortization_years: Optional[int] = None       # e.g. 25
    monthly_rent_override: Optional[float] = None  # LTR manual override
    nightly_rate_override: Optional[float] = None  # STR manual override

    # STR cost overrides — for the cohost commission and cleaning sliders
    str_management_fee_pct: Optional[float] = None  # e.g. 0.25 for 25% cohost commission
    str_cleaning_pct: Optional[float] = None        # e.g. 0.10 for 10% of revenue


class InvestmentCalculatorRequest(BaseModel):
    purchase_price: float
    annual_revenue: float
    annual_expenses: float
    interest_rate: Optional[float] = None
    down_payment_pct: Optional[float] = None
    amortization_years: Optional[int] = None
    property_tax_annual: Optional[float] = None
    analysis_type: AnalysisType = AnalysisType.BOTH


class RentInsightRequest(BaseModel):
    community: str = Field(..., description="Calgary community name (e.g. Beltline)")
    bedrooms: int = Field(..., ge=0, le=6)
    property_type: Optional[str] = "Apartment"    # Apartment, House, Condo, Townhouse
    square_footage: Optional[float] = None


class NeighborhoodInsightRequest(BaseModel):
    community: str
    include_str_data: bool = True
    include_ltr_data: bool = True
    include_demographics: bool = False


# ─────────────────────────────────────────
# RESPONSE MODELS
# ─────────────────────────────────────────

class PropertyDetails(BaseModel):
    mls_number: str
    address: str
    community: str
    city: str
    province: str
    postal_code: Optional[str] = None
    list_price: float
    bedrooms: int
    bathrooms: float
    square_footage: Optional[float] = None
    property_type: str
    year_built: Optional[int] = None
    lot_size: Optional[float] = None
    parking: Optional[int] = None
    listing_url: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class MortgageBreakdown(BaseModel):
    purchase_price: float
    down_payment: float
    down_payment_pct: float
    loan_amount: float
    interest_rate: float
    amortization_years: int
    monthly_payment: float
    annual_payment: float


class LTRAnalysis(BaseModel):
    estimated_monthly_rent: float
    annual_gross_revenue: float
    vacancy_allowance: float
    effective_gross_income: float

    # Expenses
    property_tax_annual: float
    insurance_annual: float
    maintenance_annual: float
    management_fee_annual: float
    utilities_annual: float
    total_annual_expenses: float

    # Returns
    noi: float
    cap_rate: float                  # As decimal e.g. 0.042
    cap_rate_display: str            # "4.2%"
    annual_cash_flow: float
    monthly_cash_flow: float
    cash_on_cash_return: float
    cash_on_cash_display: str        # "6.1%"
    gross_rent_multiplier: float


class STRAnalysis(BaseModel):
    estimated_nightly_rate: float
    estimated_occupancy_rate: float  # decimal e.g. 0.68
    annual_gross_revenue: float
    vacancy_allowance: float
    effective_gross_income: float

    # Expenses
    airbnb_host_fee_annual: float
    cleaning_costs_annual: float
    property_tax_annual: float
    insurance_annual: float          # STR insurance is higher
    maintenance_annual: float
    management_fee_annual: float
    supplies_annual: float
    total_annual_expenses: float

    # Returns
    noi: float
    cap_rate: float
    cap_rate_display: str
    annual_cash_flow: float
    monthly_cash_flow: float
    cash_on_cash_return: float
    cash_on_cash_display: str

    # STR-specific
    nearby_airbnbs: Optional[List[Dict[str, Any]]] = []
    avg_neighbourhood_nightly_rate: Optional[float] = None
    avg_neighbourhood_occupancy: Optional[float] = None
    is_turnkey_active: bool = False   # True if listing also found on Airbnb


class InvestmentSummary(BaseModel):
    recommendation: str              # "Strong Buy", "Buy", "Hold", "Avoid"
    confidence: str                  # "High", "Medium", "Low"
    best_strategy: str               # "LTR" or "STR"
    key_insight: str                 # One-line human-readable takeaway
    ai_narrative: Optional[str] = None


class AnalyzeListingResponse(BaseModel):
    property: PropertyDetails
    mortgage: MortgageBreakdown
    ltr: Optional[LTRAnalysis] = None
    str_analysis: Optional[STRAnalysis] = None
    summary: InvestmentSummary
    report_id: Optional[str] = None  # Supabase row ID for saved reports


class RentInsightResponse(BaseModel):
    community: str
    bedrooms: int
    property_type: str
    avg_rent: float
    low_rent: float
    high_rent: float
    median_rent: float
    yoy_change_pct: float
    sample_size: int
    last_updated: str
    comparable_listings: List[Dict[str, Any]] = []


class NeighborhoodInsightResponse(BaseModel):
    community: str
    city: str
    overview: str
    ltr_avg_rent_by_bedroom: Dict[str, float]
    str_avg_nightly_by_bedroom: Dict[str, float]
    str_avg_occupancy: float
    avg_cap_rate_ltr: float
    avg_cap_rate_str: float
    active_listings: int
    avg_days_on_market: int
    median_sale_price: float
    price_per_sqft: float
    yoy_appreciation: float
    walkability_score: Optional[int] = None
    transit_score: Optional[int] = None
