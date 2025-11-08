# database.py
import os
import asyncpg # type: ignore
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv
from app.logger import setup_logger
logger = setup_logger()
from app.database_service.models import Base
load_dotenv()

# Get database URL from environment
API_BASE_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if API_BASE_URL:
    # logger.info("using prod")
    DATABASE_URL = os.getenv("DATABASE_URL_PROD")
else:
    # logger.info("using dev")
    DATABASE_URL = os.getenv("DATABASE_URL_DEV")

# logger.info(DATABASE_URL)

# Replace postgresql:// with postgresql+asyncpg:// for async support
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Create async engine
engine = create_async_engine(ASYNC_DATABASE_URL, echo=True) # type: ignore

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine, # type: ignore
    class_=AsyncSession,
    expire_on_commit=False
) # type: ignore

# Database connection pool for raw SQL
async def get_db_pool():
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10,  # Adjust based on your needs
        max_inactive_connection_lifetime=300,  # Close idle connections after 5 minutes
        statement_cache_size=0 
    )
    return pool

# Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as session: # type: ignore
        try:
            yield session
        finally:
            await session.close()

# Create tables function
async def create_tables():
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # logger.info("✅ Database tables created successfully")