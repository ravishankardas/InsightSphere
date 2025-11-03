# app/core/rate_limiter_config.py

import os
from fastapi import Request
from slowapi import Limiter # type: ignore
from slowapi.util import get_ipaddr # type: ignore

# Function to extract the user identifier for rate limiting
def get_user_identifier(request: Request) -> str:
    """Prioritizes the X-User-Id header (email/Clerk ID), falls back to IP."""
    user_id = request.headers.get("x-user-id")
    if user_id:
        return user_id
    # Fallback to IP address if X-User-Id is missing
    return get_ipaddr(request)

# Initialize the Limiter: 
# 2/86400 is 2 queries per 24 hours (86400 seconds)
REDIS_STORAGE_URI = os.getenv("REDIS_URI", "memory://")
to_ = os.getenv("TO", "2")
from_ = os.getenv("FROM", "86400")
limiter = Limiter(
    key_func=get_user_identifier, 
    default_limits=[f"{to_}/{from_}"], 
    storage_uri=REDIS_STORAGE_URI # Use Redis URI for production
)

# Export this function for use in main.py
def get_limiter() -> Limiter:
    return limiter