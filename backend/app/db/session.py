from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Async engine (used by FastAPI)
async_engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

# Sync engine (used by Alembic)
sync_engine = create_engine(settings.database_url_sync, echo=False)
SyncSessionLocal = sessionmaker(sync_engine)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
