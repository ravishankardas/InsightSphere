# app/services/document_manager.py

from typing import List
from app.logger import setup_logger
import asyncpg # type: ignore
import os
from app.services.ingest import get_user_collection

from dotenv import load_dotenv


load_dotenv()
logger = setup_logger()

async def get_user_documents_from_db(user_id: str) -> List[str]:
    """
    Retrieves a unique list of document names from PostgreSQL chat_conversations table.
    """
    try:
        DATABASE_URL = os.getenv("DATABASE_URL_PROD")
        
        if not DATABASE_URL:
            logger.error("DATABASE_URL_PROD environment variable is not set")
            return []
            
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Get distinct document names for this user
            rows = await conn.fetch(
                "SELECT DISTINCT document_name FROM chat_conversations WHERE user_id = $1 ORDER BY document_name",
                user_id.lower()
            )
            document_names = [row['document_name'] for row in rows]
            
            logger.info(f"📄 Found {len(document_names)} documents in PostgreSQL for user {user_id}")
            return document_names
            
        finally:
            await conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching documents from PostgreSQL for user {user_id}: {e}")
        return []


def delete_document(user_id: str, filename: str) -> bool:
    """
    Permanently deletes a document and all its associated chunks from ChromaDB.
    Returns True only if successful, False if failed.
    """
    try:
        collection = get_user_collection(user_id)
        if not collection:
            logger.error(f"❌ Collection not found for user {user_id}")
            return False
        
        # Count chunks before deletion for logging
        pre_count = collection.count(
            where={ # type: ignore
                "$and": [
                    {"user_id": user_id},
                    {"source": filename}
                ]
            }
        )
        
        if pre_count == 0:
            logger.warning(f"📭 No chunks found to delete for document {filename}")
            return True  # Consider this success - nothing to delete
            
        # Perform deletion
        collection.delete(
            where={
                "$and": [ 
                    {"user_id": user_id},
                    {"source": filename}
                ]
            }
        )
        
        # Verify deletion
        post_count = collection.count(
            where={ # type: ignore
                "$and": [
                    {"user_id": user_id},
                    {"source": filename}
                ]
            }
        )
        
        success = post_count == 0
        if success:
            logger.info(f"✅ Successfully deleted {pre_count} chunks for document {filename}")
        else:
            logger.error(f"❌ Deletion verification failed: {post_count} chunks remaining")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Error deleting document {filename} for user {user_id}: {e}")
        return False

# Remove ChromaDB functions since we're only using PostgreSQL
# The following functions are no longer needed:
# - get_user_documents() 
# - delete_document()


async def get_documents_in_chromadb(user_id: str) -> List[str]:
    """
    Get list of documents that actually exist in ChromaDB with content
    """
    try:
        collection = get_user_collection(user_id)
        if not collection:
            return []
            
        # Get all items from ChromaDB for this user
        results = collection.get(
            where={"user_id": user_id},
            include=['metadatas']
        )
        
        # Extract unique source documents
        documents = set()
        if results['metadatas']:
            for metadata in results['metadatas']: # type: ignore
                if metadata and 'source' in metadata:
                    documents.add(metadata['source'])
        
        logger.info(f"🔍 ChromaDB has {len(documents)} documents for user {user_id}")
        return sorted(list(documents))
        
    except Exception as e:
        logger.error(f"Error getting ChromaDB documents for {user_id}: {e}")
        return []
    


async def document_exists_in_chromadb(user_id: str, filename: str) -> bool:
    """
    Check if a document actually exists in ChromaDB before deletion
    """
    try:
        collection = get_user_collection(user_id)
        if not collection:
            return False
            
        # Check if any chunks exist for this document
        results = collection.get(
            where={
                "$and": [
                    {"user_id": user_id},
                    {"source": filename}
                ]
            },
            limit=1  # We only need to know if at least one exists
        )
        
        exists = len(results['ids']) > 0 if results and 'ids' in results else False
        logger.info(f"🔍 Document {filename} exists in ChromaDB: {exists}")
        return exists
        
    except Exception as e:
        logger.error(f"Error checking document existence for {filename}: {e}")
        return False