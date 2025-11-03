from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import upload, query

app = FastAPI(
    title="InsightSphere API", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration - MUST be added before routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://theinsightsphere.xyz",  # Your production frontend
        "https://www.theinsightsphere.xyz",  # www version
        "https://insight-sphere-lake.vercel.app",  # Vercel deployment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers AFTER middleware
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(query.router, prefix="/api/query", tags=["Query"])

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