# main.py (Updated to use app/core/rate_limiter_config.py)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

# --- FIX: Import limiter from the new config file ---
from app.core.rate_limiter_config import limiter
from slowapi.errors import RateLimitExceeded # type: ignore
# ----------------------------------------------------

from app.api import upload, query, documents # These imports are now safe

app = FastAPI(
    title="InsightSphere API", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Attach the limiter instance to the app state
app.state.limiter = limiter

# Add exception handler for rate limit exceeded errors
@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler to return a 429 response when limit is exceeded."""
    limit_string = str(exc.detail).split(":")[-1].strip()
    return JSONResponse(
        content={
            "detail": f"Rate limit exceeded: You are limited to 2 queries per 24 hour period. Please try again later.",
            "answer": "Query limit exceeded. Please try again later."
        },
        status_code=HTTP_429_TOO_MANY_REQUESTS,
    )


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://theinsightsphere.xyz",
        "https://www.theinsightsphere.xyz",
        "https://insight-sphere-lake.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
     allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-User-Id",
        "X-API-Key",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials",
    ],
    expose_headers=["*"],
)

# Include routers AFTER middleware
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(query.router, prefix="/api/query", tags=["Query"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "InsightSphere API",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "InsightSphere API is running"}