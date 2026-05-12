"""
AirRev Engine — Security
API key validation so only your Lovable frontend can call this
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-AirRev-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_header)):
    """
    Validates the X-AirRev-Key header.
    Set this key in Lovable's Secrets and include it in every request.
    """
    if settings.APP_ENV == "development":
        return True  # Skip auth in local dev

    if not api_key or api_key != settings.AIRREV_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key. Set X-AirRev-Key header.",
        )
    return True
