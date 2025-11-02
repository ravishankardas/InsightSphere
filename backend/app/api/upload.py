from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from typing import Optional
from app.services.ingest import ingest_pdf
from app.services.multimodal_ingest import ingest_multimodal_pdf  # NEW

router = APIRouter()

@router.post("/pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Auth required")
    
    filename = (file.filename or "").lower()
    if not filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDFs")
    
    contents = await file.read()
    result = ingest_multimodal_pdf(contents, user_id, filename )
    
    return {
        "status": "indexed",
        "text_chunks": result["n_chunks"],
        "tables": result["n_tables"],
        "images": result["n_images"],
        "total": result["total_items"]
    }