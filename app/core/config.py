"""
AirRev Engine — Configuration
All secrets via environment variables / .env file
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # --- App ---
    APP_ENV: str = "development"
    API_SECRET_KEY: str = "change-me-in-production"

    # --- CREA DDF ---
    DDF_API_URL: str = "https://ddfapi.realtor.ca/odata/v1"
    DDF_ACCESS_KEY: str = ""
    DDF_SECRET_KEY: str = ""

    # --- Supabase ---
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # --- Email ---
    EMAIL_PROVIDER: str = "resend"          # resend | sendgrid | smtp
    EMAIL_FROM: str = "reports@airrev.io"
    EMAIL_FROM_NAME: str = "AirRev.io Reports"
    RESEND_API_KEY: str = ""
    SENDGRID_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # --- STR / Airbnb Data Sources ---
    AIRDNA_API_KEY: str = ""                # https://www.airdna.co/api (not in use)
    AIRROI_API_KEY: str = ""                # https://www.airroi.com/api (primary)
    AIRROI_API_URL: str = "https://api.airroi.com"

    # --- AI (optional) ---
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AI_ENABLED: bool = False

    # --- CORS ---
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://airrev.io",
        "https://*.lovable.app",
    ]

    # --- Calgary-specific defaults ---
    DEFAULT_PROPERTY_TAX_RATE: float = 0.0099       # 0.99% Calgary mill rate
    DEFAULT_INTEREST_RATE: float = 0.0599            # ~6% Canadian mortgage
    DEFAULT_AMORTIZATION_YEARS: int = 25             # Canadian standard (not 30)
    DEFAULT_DOWN_PAYMENT_PCT: float = 0.20
    DEFAULT_VACANCY_RATE_LTR: float = 0.04           # 4% Calgary LTR vacancy
    DEFAULT_VACANCY_RATE_STR: float = 0.30           # 30% STR vacancy (conservative)
    DEFAULT_MANAGEMENT_FEE_LTR: float = 0.10         # 10% PM fee for LTR
    DEFAULT_AIRBNB_HOST_FEE: float = 0.03            # 3% Airbnb host fee
    DEFAULT_STR_CLEANING_PER_STAY: float = 125.0     # CAD (legacy, keep for compat)
    DEFAULT_STR_STAYS_PER_MONTH: float = 8.0         # legacy, keep for compat

    # --- AirRev STR cohost defaults (overridable from frontend) ---
    DEFAULT_STR_MANAGEMENT_FEE: float = 0.25         # 25% cohost commission
    DEFAULT_STR_CLEANING_PCT: float = 0.10           # 10% of revenue for cleaning

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
