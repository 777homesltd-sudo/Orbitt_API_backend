"""
AirRev Engine — Investment Calculator Service
All the financial math: Cap Rate, CoC Return, Cash Flow, GRM
Canadian-specific: 25yr amortization, Calgary property tax rates
"""

import math
from typing import Optional
from app.core.config import settings
from app.models.schemas import (
    MortgageBreakdown,
    LTRAnalysis,
    STRAnalysis,
    InvestmentSummary,
    PropertyDetails,
    AnalysisType,
)


class InvestmentCalculator:

    def __init__(self):
        self.cfg = settings

    # ──────────────────────────────────────
    # MORTGAGE
    # ──────────────────────────────────────

    def calculate_mortgage(
        self,
        purchase_price: float,
        interest_rate: Optional[float] = None,
        down_payment_pct: Optional[float] = None,
        amortization_years: Optional[int] = None,
    ) -> MortgageBreakdown:
        rate = interest_rate or self.cfg.DEFAULT_INTEREST_RATE
        dp_pct = down_payment_pct or self.cfg.DEFAULT_DOWN_PAYMENT_PCT
        amort = amortization_years or self.cfg.DEFAULT_AMORTIZATION_YEARS

        down_payment = purchase_price * dp_pct
        loan_amount = purchase_price - down_payment

        # Canadian mortgage: semi-annual compounding converted to monthly
        # Effective annual rate from semi-annual: (1 + r/2)^2 - 1
        semi_annual_rate = rate / 2
        effective_annual = (1 + semi_annual_rate) ** 2 - 1
        monthly_rate = (1 + effective_annual) ** (1 / 12) - 1

        n = amort * 12
        if monthly_rate > 0:
            monthly_payment = (
                loan_amount * monthly_rate * (1 + monthly_rate) ** n
            ) / ((1 + monthly_rate) ** n - 1)
        else:
            monthly_payment = loan_amount / n

        return MortgageBreakdown(
            purchase_price=purchase_price,
            down_payment=round(down_payment, 2),
            down_payment_pct=dp_pct,
            loan_amount=round(loan_amount, 2),
            interest_rate=rate,
            amortization_years=amort,
            monthly_payment=round(monthly_payment, 2),
            annual_payment=round(monthly_payment * 12, 2),
        )

    # ──────────────────────────────────────
    # PROPERTY TAX ESTIMATE
    # ──────────────────────────────────────

    def estimate_property_tax(self, purchase_price: float, community: str = "") -> float:
        """
        Calgary 2024 residential mill rate ≈ 0.99% of assessed value.
        Assessed value is typically 85-95% of market value.
        """
        assessed_value = purchase_price * 0.90  # 90% of purchase as assessed
        return round(assessed_value * self.cfg.DEFAULT_PROPERTY_TAX_RATE, 2)

    # ──────────────────────────────────────
    # LTR ANALYSIS
    # ──────────────────────────────────────

    def calculate_ltr(
        self,
        property: PropertyDetails,
        mortgage: MortgageBreakdown,
        monthly_rent: float,
        vacancy_rate: Optional[float] = None,
    ) -> LTRAnalysis:
        vacancy = vacancy_rate or self.cfg.DEFAULT_VACANCY_RATE_LTR
        price = property.list_price

        # Revenue
        annual_gross = monthly_rent * 12
        vacancy_allowance = annual_gross * vacancy
        egi = annual_gross - vacancy_allowance  # Effective Gross Income

        # Expenses
        property_tax = self.estimate_property_tax(price, property.community)
        insurance = price * 0.003             # ~0.3% for LTR landlord insurance
        maintenance = price * 0.01            # 1% rule for maintenance reserve
        mgmt_fee = egi * self.cfg.DEFAULT_MANAGEMENT_FEE_LTR
        utilities = 0                         # Tenant pays in most Calgary LTR

        total_expenses = property_tax + insurance + maintenance + mgmt_fee + utilities
        noi = egi - total_expenses

        # Returns
        cap_rate = noi / price if price > 0 else 0
        annual_cash_flow = noi - mortgage.annual_payment
        monthly_cash_flow = annual_cash_flow / 12
        coc = annual_cash_flow / mortgage.down_payment if mortgage.down_payment > 0 else 0
        grm = price / annual_gross if annual_gross > 0 else 0

        return LTRAnalysis(
            estimated_monthly_rent=monthly_rent,
            annual_gross_revenue=round(annual_gross, 2),
            vacancy_allowance=round(vacancy_allowance, 2),
            effective_gross_income=round(egi, 2),
            property_tax_annual=round(property_tax, 2),
            insurance_annual=round(insurance, 2),
            maintenance_annual=round(maintenance, 2),
            management_fee_annual=round(mgmt_fee, 2),
            utilities_annual=round(utilities, 2),
            total_annual_expenses=round(total_expenses, 2),
            noi=round(noi, 2),
            cap_rate=round(cap_rate, 4),
            cap_rate_display=f"{round(cap_rate * 100, 2)}%",
            annual_cash_flow=round(annual_cash_flow, 2),
            monthly_cash_flow=round(monthly_cash_flow, 2),
            cash_on_cash_return=round(coc, 4),
            cash_on_cash_display=f"{round(coc * 100, 2)}%",
            gross_rent_multiplier=round(grm, 2),
        )

    # ──────────────────────────────────────
    # STR ANALYSIS
    # ──────────────────────────────────────

    def calculate_str(
        self,
        property: PropertyDetails,
        mortgage: MortgageBreakdown,
        nightly_rate: float,
        occupancy_rate: Optional[float] = None,
        nearby_airbnbs: Optional[list] = None,
        management_fee_pct: Optional[float] = None,
        cleaning_pct: Optional[float] = None,
    ) -> STRAnalysis:
        price = property.list_price
        occupancy = occupancy_rate if occupancy_rate is not None else 0.70

        # Allow per-request overrides; fall back to config defaults
        mgmt_pct = (
            management_fee_pct
            if management_fee_pct is not None
            else self.cfg.DEFAULT_STR_MANAGEMENT_FEE
        )
        clean_pct = (
            cleaning_pct
            if cleaning_pct is not None
            else self.cfg.DEFAULT_STR_CLEANING_PCT
        )

        # Revenue (nights booked)
        nights_booked_per_year = 365 * occupancy
        annual_gross = nightly_rate * nights_booked_per_year
        vacancy_allowance = annual_gross * (1 - occupancy)
        egi = annual_gross

        # Expenses (STR has more ops costs)
        airbnb_fee = egi * self.cfg.DEFAULT_AIRBNB_HOST_FEE
        cleaning = egi * clean_pct                   # 10% of revenue by default
        property_tax = self.estimate_property_tax(price, property.community)
        insurance = price * 0.005                    # STR insurance ~0.5% (higher than LTR)
        maintenance = price * 0.015                  # Higher wear and tear
        mgmt_fee = egi * mgmt_pct                    # 25% cohost commission by default
        supplies = 1200                              # Toiletries, linens replacement annual

        total_expenses = (
            airbnb_fee + cleaning + property_tax + insurance
            + maintenance + mgmt_fee + supplies
        )
        noi = egi - total_expenses

        # Returns
        cap_rate = noi / price if price > 0 else 0
        annual_cash_flow = noi - mortgage.annual_payment
        monthly_cash_flow = annual_cash_flow / 12
        coc = annual_cash_flow / mortgage.down_payment if mortgage.down_payment > 0 else 0

        # Neighbourhood comps
        avg_neighbourhood_nightly = None
        avg_neighbourhood_occ = None
        is_turnkey = False

        if nearby_airbnbs:
            rates = [a.get("nightly_rate", 0) for a in nearby_airbnbs if a.get("nightly_rate")]
            occs = [a.get("occupancy_rate", 0) for a in nearby_airbnbs if a.get("occupancy_rate")]
            avg_neighbourhood_nightly = round(sum(rates) / len(rates), 2) if rates else None
            avg_neighbourhood_occ = round(sum(occs) / len(occs), 4) if occs else None
            is_turnkey = any(a.get("is_active_airbnb") for a in nearby_airbnbs)

        return STRAnalysis(
            estimated_nightly_rate=nightly_rate,
            estimated_occupancy_rate=occupancy,
            annual_gross_revenue=round(annual_gross, 2),
            vacancy_allowance=round(vacancy_allowance, 2),
            effective_gross_income=round(egi, 2),
            airbnb_host_fee_annual=round(airbnb_fee, 2),
            cleaning_costs_annual=round(cleaning, 2),
            property_tax_annual=round(property_tax, 2),
            insurance_annual=round(insurance, 2),
            maintenance_annual=round(maintenance, 2),
            management_fee_annual=round(mgmt_fee, 2),
            supplies_annual=round(supplies, 2),
            total_annual_expenses=round(total_expenses, 2),
            noi=round(noi, 2),
            cap_rate=round(cap_rate, 4),
            cap_rate_display=f"{round(cap_rate * 100, 2)}%",
            annual_cash_flow=round(annual_cash_flow, 2),
            monthly_cash_flow=round(monthly_cash_flow, 2),
            cash_on_cash_return=round(coc, 4),
            cash_on_cash_display=f"{round(coc * 100, 2)}%",
            nearby_airbnbs=nearby_airbnbs or [],
            avg_neighbourhood_nightly_rate=avg_neighbourhood_nightly,
            avg_neighbourhood_occupancy=avg_neighbourhood_occ,
            is_turnkey_active=is_turnkey,
        )

    # ──────────────────────────────────────
    # INVESTMENT SUMMARY
    # ──────────────────────────────────────

    def generate_summary(
        self,
        ltr: Optional[LTRAnalysis],
        str_analysis: Optional[STRAnalysis],
        analysis_type: AnalysisType,
    ) -> InvestmentSummary:
        """
        Human-readable investment recommendation based on the numbers.
        """
        best_strategy = "LTR"
        best_coc = ltr.cash_on_cash_return if ltr else -99
        best_cap = ltr.cap_rate if ltr else 0

        if str_analysis and str_analysis.cash_on_cash_return > best_coc:
            best_strategy = "STR"
            best_coc = str_analysis.cash_on_cash_return
            best_cap = str_analysis.cap_rate

        # Recommendation thresholds (Canadian market calibrated)
        if best_coc >= 0.08:
            recommendation = "Strong Buy"
            confidence = "High"
        elif best_coc >= 0.04:
            recommendation = "Buy"
            confidence = "Medium"
        elif best_coc >= 0.0:
            recommendation = "Hold"
            confidence = "Medium"
        else:
            recommendation = "Avoid"
            confidence = "High"

        # Key insight
        if best_coc < 0:
            key_insight = (
                f"Negative cash flow of C${abs(ltr.monthly_cash_flow if ltr else 0):,.0f}/mo. "
                f"Consider {'STR strategy' if best_strategy == 'LTR' else 'price negotiation'} "
                f"or larger down payment to improve returns."
            )
        elif best_coc < 0.05:
            key_insight = (
                f"Modest {best_cap * 100:.1f}% cap rate. Viable long-term hold "
                f"with appreciation potential in {best_strategy} configuration."
            )
        else:
            key_insight = (
                f"Strong {best_coc * 100:.1f}% cash-on-cash return as {best_strategy}. "
                f"Cap rate of {best_cap * 100:.1f}% beats Calgary average."
            )

        return InvestmentSummary(
            recommendation=recommendation,
            confidence=confidence,
            best_strategy=best_strategy,
            key_insight=key_insight,
        )


# Singleton
calculator = InvestmentCalculator()
