# app/api/documents.py

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List
from app.core.auth import validate_api_key 
from app.database_service.db_service import load_all_chats_from_db, delete_chat_from_db
from app.logger import setup_logger

logger = setup_logger()
router = APIRouter(dependencies=[Depends(validate_api_key)]) # Enforce API Key Auth

@router.get("", response_model=List[str])
async def list_documents(
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        # 1. Get documents from PostgreSQL chat history
        chats = await load_all_chats_from_db(user_id.lower())
        postgres_documents = sorted(list(chats.keys()))
        
        # 2. Get documents that actually exist in ChromaDB
        from app.services.document_manager import get_documents_in_chromadb
        chroma_documents = await get_documents_in_chromadb(user_id.lower())
        
        # 3. Only return documents that exist in BOTH databases
        valid_documents = [doc for doc in postgres_documents if doc in chroma_documents]
        
        logger.info(f"📋 User {user_id}: {len(postgres_documents)} in PostgreSQL, {len(chroma_documents)} in ChromaDB, {len(valid_documents)} valid")
        
        return valid_documents
        
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch documents")
    

@router.delete("/{filename}", summary="Delete a specific document and its data from both databases")
async def delete_document_by_filename(
    filename: str,
    user_id: str = Header(None, alias="X-User-Id")
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        # 1. FIRST verify the document exists in ChromaDB
        from app.services.document_manager import document_exists_in_chromadb
        if not await document_exists_in_chromadb(user_id.lower(), filename.lower()):
            logger.warning(f"⚠️ Document '{filename}' not found in ChromaDB for user {user_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Document '{filename}' not found or already deleted"
            )

        # 2. Delete from ChromaDB FIRST
        from app.services.document_manager import delete_document
        chroma_success = delete_document(user_id.lower(), filename.lower())
        
        if not chroma_success:
            logger.error(f"❌ Failed to delete document '{filename}' from ChromaDB")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to delete document '{filename}' from storage"
            )

        # 3. Only AFTER ChromaDB success, delete chat history
        from app.database_service.db_service import delete_chat_from_db
        await delete_chat_from_db(user_id.lower(), filename.lower())
        
        logger.info(f"✅ Fully deleted document '{filename}' for user {user_id}")
        return {"message": f"Document '{filename}' and all associated data deleted successfully."}
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404, 500)
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting document {filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )