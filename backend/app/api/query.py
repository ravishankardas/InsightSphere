import time
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Assuming this path is correct based on your previous file:
from app.services.multimodal_retriever import query_multimodal 
from app.core.rate_limiter_config import limiter
from app.services.evaluation import evaluate_rag_pipeline
from app.core.auth import validate_api_key

# --- NEW IMPORT ---
from app.api.analytics import log_query
from app.services.query_rewriter import get_query_rewriter
from app.services.intent_classifier import detect_email_intent
# ------------------
from dotenv import load_dotenv
import os

load_dotenv()

TO_ = os.getenv("TO") 

router = APIRouter(dependencies=[Depends(validate_api_key)])
# router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 4
    source: str = ""
    use_query_rewriting: bool = True

@router.post("")
@limiter.limit(f"{TO_}/24hour")
async def query_documents(
    request: Request,
    body: QueryRequest,
    user_id: str = Header(None, alias="X-User-Id")
) -> Dict[str, Any]:
    """
    Query your uploaded documents and log performance metrics.
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    start_time = time.time()
    result = {} # Initialize result to ensure it's available in finally block
    
    # Initialize log data with assumed failure (error: True)
    log_data = {
        "user_id": user_id,
        "query": body.query,
        "document_queried": [body.source] if body.source else [], # Initial placeholder
        "error": True, 
        "response_time_ms": None,
    }
    # intent = detect_email_intent(body.query)
    # from icecream import ic
    # ic(intent)
    # ic(user_id)

    # if intent.send_email:
    #     return {
    #         "answer": "Email Sent Successfully",
    #         "sources": [body.source],
    #         "query": body.query
    #     }
    # else:
    #     pass

    email_present = False
    query_rewriter = get_query_rewriter()
    try:
        processed_query = body.query
        search_query = body.query.lower()

        if not any(keyword in search_query for keyword in ["email", "mail"]):
            if body.use_query_rewriting:
                # Check if query needs rewriting
                if query_rewriter.should_rewrite(body.query):
                    processed_query = query_rewriter.rewrite_query(
                        original_query=body.query,
                    )
                    print(f"✏️ Query rewritten: '{body.query}' → '{processed_query}'")
            pass
        else:
            print("Not rewriting query as it seems to be email related.")
            email_present = True

        # print(f"body: {body}")
        # Pass source filter to query function
        result = await query_multimodal(
            processed_query, 
            user_id, 
            body.top_k,
            source_filter=body.source, # type: ignore
            email_present=email_present  # type: ignore
        )
        
        # Log successful query sources (the sources returned by RAG are filenames/strings)
        log_data["document_queried"] = result.get("sources", [])
        
        # Check for success: if an answer exists and it doesn't contain a typical error/failure message
        answer_text = result.get("answer", "").lower()
        if result.get("answer") and "error" not in answer_text and "no documents" not in answer_text and "not configured" not in answer_text:
            log_data["error"] = False

        return result

    except Exception as e:
        print(f"Query exception: {e}")
        return {"answer": f"A system error occurred during the query: {e}", "sources": [], "citations": []}

    finally:
        # Log the operation regardless of success or failure
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        log_data["response_time_ms"] = round(response_time_ms, 2)
        
        # Final log write
        log_query(log_data)


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