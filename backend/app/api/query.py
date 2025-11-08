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
from app.logger import setup_logger
from app.database_service.db_service import load_chat_from_db, save_chat_to_db

load_dotenv()


logger = setup_logger()

TO_ = os.getenv("TO") 

router = APIRouter(dependencies=[Depends(validate_api_key)])
# router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 4
    source: str = ""
    use_query_rewriting: bool = True


# Request/Response models for chat saving
class ChatMessage(BaseModel):
    type: str  # "user" or "assistant" or "error"
    content: str
    isUser: bool
    timestamp: str
    retrieved: Optional[List[Dict[str, Any]]] = None

class SaveChatRequest(BaseModel):
    document_name: str
    messages: List[ChatMessage]

class SaveChatResponse(BaseModel):
    success: bool
    message: str
    document_name: Optional[str] = None

class LoadChatResponse(BaseModel):
    success: bool
    messages: List[Dict[str, Any]]
    document_name: Optional[str] = None

@router.post("")
# @limiter.limit(f"{TO_}/24hour")
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

        if "Previous conversation:" in processed_query and "Current question:" in processed_query:
            logger.info("🧠 Memory context detected - using enhanced query")
            logger.info(f"Enhanced query length: {len(processed_query)}")
        elif any(keyword in search_query for keyword in ["email", "mail"]):
            logger.info("Not rewriting query as it seems to be email related.")
            email_present = True
        else:
            if body.use_query_rewriting and query_rewriter.should_rewrite(body.query):
                processed_query = query_rewriter.rewrite_query(
                    original_query=body.query,
                )
                logger.info(f"✏️ Query rewritten: '{body.query}' → '{processed_query}'")

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
        logger.error(f"Query exception: {e}")
        return {"answer": f"A system error occurred during the query: {e}", "sources": [], "citations": []}

    finally:
        # Log the operation regardless of success or failure
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        log_data["response_time_ms"] = round(response_time_ms, 2)
        
        # Final log write
        log_query(log_data)

# Add this to your existing router in query.py
@router.post("/chats/save")
async def save_chat_conversation(
    request: Request,
    body: SaveChatRequest,
    user_id: str = Header(None, alias="X-User-Id")
):
    """
    Save chat conversation for a specific document
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    if not body.document_name:
        raise HTTPException(
            status_code=400,
            detail="Document name is required."
        )
    
    logger.info(f"💾 Saving chat for user {user_id}, document: {body.document_name}, messages: {len(body.messages)}")
    
    try:
        # Convert Pydantic models to dict for JSON storage
        messages_dict = [message.dict() for message in body.messages]
        
        # Save to database
        await save_chat_to_db(user_id, body.document_name, messages_dict)
        
        return SaveChatResponse(
            success=True,
            message="Chat conversation saved successfully",
            document_name=body.document_name
        )
        
    except Exception as e:
        logger.error(f"❌ Error saving chat: {e}")
        return SaveChatResponse(
            success=False,
            message=f"Failed to save chat: {str(e)}"
        )

@router.get("/chats/load/{document_name}")
async def load_chat_conversation(
    document_name: str,
    user_id: str = Header(None, alias="X-User-Id")
):
    """
    Load chat conversation for a specific document
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    logger.info(f"📂 Loading chat for user {user_id}, document: {document_name}")
    
    try:
        messages = await load_chat_from_db(user_id, document_name)
        
        return LoadChatResponse(
            success=True,
            messages=messages,
            document_name=document_name
        )
        
    except Exception as e:
        logger.error(f"❌ Error loading chat: {e}")
        return LoadChatResponse(
            success=False,
            messages=[],
            document_name=document_name
        )

@router.delete("/chats/delete/{document_name}")
async def delete_chat_conversation(
    document_name: str,
    user_id: str = Header(None, alias="X-User-Id")
):
    """
    Delete chat conversation AND document content from ChromaDB
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    logger.info(f"🗑️ Deleting chat and document for user {user_id}, document: {document_name}")
    
    try:
        # Import your services
        from app.database_service.db_service import delete_chat_from_db
        from app.services.document_manager import delete_document
        
        # 1. Delete chat history from PostgreSQL
        await delete_chat_from_db(user_id, document_name)
        logger.info(f"✅ Chat history deleted from PostgreSQL for {document_name}")
        
        # 2. Delete document content from ChromaDB
        chroma_success = delete_document(user_id, document_name)
        
        if chroma_success:
            logger.info(f"✅ Document content deleted from ChromaDB for {document_name}")
        else:
            logger.warning(f"⚠️ Document not found in ChromaDB for {document_name}")
        
        return {
            "success": True,
            "message": "Document and chat history deleted successfully",
            "document_name": document_name,
            "chroma_deleted": chroma_success
        }
        
    except Exception as e:
        logger.error(f"❌ Error deleting document {document_name}: {e}")
        return {
            "success": False,
            "message": f"Failed to delete document: {str(e)}"
        }
        
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
    
    logger.info(f"\n⚡ RAGAs Evaluation triggered for user: {user_id}")
    
    # Call the new evaluation service
    result = evaluate_rag_pipeline(user_id, file_name) 
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result