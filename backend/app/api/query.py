from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
from app.services.retriever import retrieve_and_answer
from app.services.multimodal_retriever import query_multimodal
from app.core.rate_limiter_config import limiter

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    top_k: int = 4
    source: Optional[str] = None  # ← Add optional source filter

@router.post("")
@limiter.limit("2/24hour")
async def query_documents(
    request: Request,
    body: QueryRequest,
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Query your uploaded documents.
    Currently uses X-User-Id header (dev mode).
    Will be replaced with email auth token.
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    # print(f"source filter from the api: {request.source}")
    # Pass source filter to query function
    result = query_multimodal(
        body.query, 
        user_id, 
        body.top_k,
        source_filter=body.source  # ← Pass the filter # type: ignore
    )
    return result