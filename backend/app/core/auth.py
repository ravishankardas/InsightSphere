# app/core/auth.py

import os
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from dotenv import load_dotenv
load_dotenv()

# 1. Define the API Key Security Scheme
# This tells FastAPI/Swagger to expect a header named 'X-API-Key'
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# 2. Define the Secret Key (use an environment variable for security)
# NOTE: Replace 'YOUR_SECRET_API_KEY' with a real environment variable or a strong static key for now.
# In a real app, this should be a robust key or a DB check.
STATIC_API_KEY = os.getenv("STATIC_MASTER_API_KEY")
# print("✓ Auth: STATIC_MASTER_API_KEY loaded from environment", STATIC_API_KEY)

async def validate_api_key(api_key: str = Security(api_key_header)):
    """
    Dependency that validates the API Key provided in the request header.
    It automatically integrates with Swagger's Authorize button.
    """
    if api_key and api_key == STATIC_API_KEY:
        # Key is valid, return it or True
        return api_key
    
    # Key is missing or invalid
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, 
        detail="Could not validate credentials: Invalid or missing API Key"
    )