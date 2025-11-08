# database_service.py
import json
from datetime import datetime
from app.logger import setup_logger
from app.database_service.database import get_db_pool
import asyncpg # type: ignore
logger = setup_logger()

import os
API_BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if API_BASE_URL:
    # logger.info("using prod")
    DATABASE_URL = os.getenv("DATABASE_URL_PROD")
else:
    # logger.info("using dev")
    DATABASE_URL = os.getenv("DATABASE_URL_DEV")

def normalize_document_name(document_name: str) -> str:
    """Normalize document name to lowercase for consistency"""
    return document_name.strip().lower()

async def get_direct_connection():
    """Get a direct connection for critical write operations"""
    return await asyncpg.connect(DATABASE_URL) # type: ignore

async def save_chat_to_db(user_id: str, document_name: str, messages: list):
    try:
        document_name = normalize_document_name(document_name)
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Check if chat already exists
            existing = await conn.fetchrow(
                "SELECT id FROM chat_conversations WHERE user_id = $1 AND document_name = $2",
                user_id, document_name
            )
            
            if existing:
                # Update existing chat
                await conn.execute(
                    """UPDATE chat_conversations 
                    SET messages = $1, updated_at = $2 
                    WHERE user_id = $3 AND document_name = $4""",
                    json.dumps(messages), datetime.utcnow(), user_id, document_name
                )
                # logger.info(f"✅ Updated chat for user {user_id}, document {document_name}")
            else:
                # Insert new chat
                await conn.execute(
                    """INSERT INTO chat_conversations 
                    (user_id, document_name, messages) 
                    VALUES ($1, $2, $3)""",
                    user_id, document_name, json.dumps(messages)
                )
                logger.info(f"✅ Created new chat for user {user_id}, document {document_name}")
                
    except Exception as e:
        logger.error(f"❌ Error saving chat to DB: {e}")
        raise

    
async def load_chat_from_db(user_id: str, document_name: str) -> list:
    """
    Load chat messages for a specific user and document (case-insensitive)
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Use LOWER() for case-insensitive search
            result = await conn.fetchrow(
                "SELECT messages, document_name FROM chat_conversations WHERE user_id = $1 AND LOWER(document_name) = LOWER($2)",
                user_id, document_name
            )
            if result:
                messages = json.loads(result["messages"])
                actual_doc_name = result["document_name"]
                logger.info(f"✅ Loaded {len(messages)} messages for {actual_doc_name}")
                return messages
            else:
                logger.info(f"ℹ️ No existing chat found for {document_name}")
                return []
    except Exception as e:
        logger.error(f"❌ Error loading chat from DB: {e}")
        return []
    
async def load_all_chats_from_db(user_id: str) -> dict:
    """
    Load all chat conversations for a user
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            results = await conn.fetch(
                "SELECT document_name, messages FROM chat_conversations WHERE user_id = $1",
                user_id
            )
            chats = {}
            for row in results:
                chats[row["document_name"]] = json.loads(row["messages"])
            logger.info(f"✅ Loaded {len(chats)} chat conversations for user {user_id}")
            return chats
    except Exception as e:
        logger.error(f"❌ Error loading all chats from DB: {e}")
        return {}

async def delete_chat_from_db(user_id: str, document_name: str):
    """
    Delete chat history for a specific user and document
    """
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chat_conversations WHERE user_id = $1 AND document_name = $2",
                user_id, document_name
            )
            logger.info(f"✅ Deleted chat history for user {user_id}, document {document_name}")
            
    except Exception as e:
        logger.error(f"❌ Error deleting chat history: {e}")
        raise