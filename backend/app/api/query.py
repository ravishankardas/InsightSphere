from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
# from app.services.retriever import retrieve_and_answer
from app.services.multimodal_retriever import query_multimodal
from app.core.rate_limiter_config import limiter
from app.services.evaluation import evaluate_rag_pipeline
from app.core.auth import validate_api_key

router = APIRouter(dependencies=[Depends(validate_api_key)])

class QueryRequest(BaseModel):
    query: str
    top_k: int = 4
    source: Optional[str] = None  

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



@router.post("/evaluate")
async def evaluate_rag(
    user_id: Optional[str] = Header(None, alias="X-User-Id"),
    file_name: str = ""
):
    """
    Triggers RAG pipeline evaluation using RAGAs and a pre-defined test set.
    Requires OPENAI_API_KEY for the evaluation LLM (gpt-3.5-turbo is used by RAGAs).
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    print(f"\n⚡ RAGAs Evaluation triggered for user: {user_id}")
    
    # Call the new evaluation service
    result = evaluate_rag_pipeline(user_id, file_name) 
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result