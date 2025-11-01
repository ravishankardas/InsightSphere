from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services.retriever import retrieve_and_answer

router = APIRouter()

class QueryRequest(BaseModel):
    query: str
    top_k: int = 4

@router.post("/")
async def query_documents(
    request: QueryRequest,
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
    
    result = retrieve_and_answer(
        query=request.query,
        user_id=user_id,
        top_k=request.top_k
    )
    return result