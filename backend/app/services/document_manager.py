# app/services/document_manager.py

from typing import List
from app.logger import setup_logger
import asyncpg # type: ignore
import os
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

# Remove ChromaDB functions since we're only using PostgreSQL
# The following functions are no longer needed:
# - get_user_documents() 
# - delete_document()