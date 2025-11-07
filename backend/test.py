# test_fix.py
import asyncio
from app.database_service.db_service import save_chat_to_db

async def test_fix():
    test_data = {
        "user_id": "test_fix_user",
        "document_name": "test_fix_document.pdf",
        "messages": [{"role": "user", "content": "Testing the fix"}]
    }
    
    print("🧪 Testing the fix...")
    await save_chat_to_db(**test_data)
    print("✅ Save operation completed")
    
    # Check in pgAdmin immediately
    input("📋 Now check pgAdmin - can you see the data? (Press Enter when done)")

asyncio.run(test_fix())