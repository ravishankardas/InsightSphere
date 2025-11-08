# app/api/documents.py

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List
from app.core.auth import validate_api_key 
from app.database_service.db_service import load_all_chats_from_db, delete_chat_from_db
from app.logger import setup_logger

logger = setup_logger()
router = APIRouter(dependencies=[Depends(validate_api_key)]) # Enforce API Key Auth

@router.get(
    "", 
    response_model=List[str], 
    summary="List all documents with chat history for the user"
)
async def list_documents(
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Fetches a unique list of document names that have chat history in PostgreSQL.
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    try:
        # Get documents from PostgreSQL chat_conversations table
        chats = await load_all_chats_from_db(user_id.lower())
        
        # Return sorted list of document names that have chat history
        document_names = sorted(list(chats.keys()))
        logger.info(f"📋 Found {len(document_names)} documents with chat history for user {user_id}")
        
        return document_names
        
    except Exception as e:
        logger.error(f"Error fetching documents from database: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch documents from database"
        )

@router.delete(
    "/{filename}", 
    summary="Delete a specific document and its data from both databases"
)
async def delete_document_by_filename(
    filename: str,
    user_id: str = Header(None, alias="X-User-Id")
):
    """
    Permanently deletes document from both ChromaDB and PostgreSQL
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )

    try:
        # Delete from ChromaDB
        from app.services.document_manager import delete_document
        chroma_success = delete_document(user_id.lower(), filename.lower())
        
        # Delete from PostgreSQL chat history
        from app.database_service.db_service import delete_chat_from_db
        await delete_chat_from_db(user_id.lower(), filename.lower())
        logger.info(f"Chat history deleted for user: {user_id.lower()} and filename: {filename.lower()}")
        
        if chroma_success:
            logger.info(f"✅ Fully deleted document '{filename}' for user {user_id}")
            return {"message": f"Document '{filename}' and all associated data deleted successfully."}
        else:
            logger.warning(f"⚠️ Document '{filename}' not found in ChromaDB, but chat history was deleted")
            return {"message": f"Chat history for '{filename}' deleted successfully."}
        
    except Exception as e:
        logger.error(f"❌ Error deleting document {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )