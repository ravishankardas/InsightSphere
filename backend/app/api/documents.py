# app/api/documents.py

from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional, List
from app.services.document_manager import get_user_documents, delete_document
# Assuming validate_api_key is available in app.core.auth
from app.core.auth import validate_api_key 

router = APIRouter(dependencies=[Depends(validate_api_key)]) # Enforce API Key Auth

@router.get(
    "", 
    response_model=List[str], 
    summary="List all uploaded documents for the user"
)
async def list_documents(
    user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Fetches a unique list of filenames (source metadata) uploaded by the user.
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )
    
    # Ensure consistency with how filenames are stored (e.g., lowercase)
    return get_user_documents(user_id.lower())

@router.delete(
    "/{filename}", 
    summary="Delete a specific document and its chunks"
)
async def delete_document_by_filename(
    filename: str,
    user_id: str = Header(None, alias="X-User-Id")
):
    """
    Permanently deletes all data chunks associated with a specific document.
    """
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide X-User-Id header."
        )

    # Ensure consistency with how filenames are stored (e.g., lowercase)
    success = delete_document(user_id.lower(), filename.lower())
    
    if not success:
        raise HTTPException(
            status_code=404, # 404 might be more appropriate if the deletion attempt fails.
            detail=f"Document '{filename}' not found or deletion failed."
        )

    return {"message": f"Document '{filename}' and all associated data deleted successfully."}