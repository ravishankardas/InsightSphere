from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional
from app.services.ingest import ingest_pdf

router = APIRouter()

@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Upload a PDF for indexing.
    Currently uses X-User-Id header (dev mode).
    Will be replaced with email auth token.
    """
    if not user_id:
        raise HTTPException(
            status_code=401, 
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    contents = await file.read()
    result = ingest_pdf(contents, user_id=user_id, filename=filename)
    
    return {
        "status": "indexed",
        "indexed_chunks": result.get("n_chunks", 0),
        "total_items": result.get("total_items", 0),
        "user_id": user_id
    }