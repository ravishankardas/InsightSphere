# database_service.py
import json
from datetime import datetime
from app.logger import setup_logger
from app.database_service.database import get_db_pool
from app.logger import setup_logger
logger = setup_logger()

async def save_chat_to_db(user_id: str, document_name: str, messages: list):
    try:
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
                logger.info(f"✅ Updated chat for user {user_id}, document {document_name}")
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
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT messages FROM chat_conversations WHERE user_id = $1 AND document_name = $2",
                user_id, document_name
            )
            if result:
                messages = json.loads(result["messages"])
                logger.info(f"✅ Loaded {len(messages)} messages for {document_name}")
                return messages
            else:
                logger.info(f"ℹ️ No existing chat found for {document_name}")
                return []
    except Exception as e:
        logger.error(f"❌ Error loading chat from DB: {e}")
        return []

async def load_all_chats_from_db(user_id: str) -> dict:
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