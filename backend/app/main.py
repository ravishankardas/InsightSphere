from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import upload, query


app = FastAPI(title="InsightSphere API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://insight-sphere-gamma.vercel.app",  # Your Vercel frontend
        "https://insightsphere-production.up.railway.app"  # Allow self
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(query.router, prefix="/api/query", tags=["Query"])

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "InsightSphere API is running"}