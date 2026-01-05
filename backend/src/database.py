from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True, future=True)


async def init_db():
    # Import models to register them with SQLModel
    from src.files.models import FileRecord
    from src.transactions.models import (
        ShandongLocalSummary, ShandongLocalTransaction,
        EverbrightSummary, EverbrightTransaction,
        CmbSummary, CmbTransaction,
        JiningSummary, JiningTransaction,
        CgbSummary, CgbTransaction,
        PsbcSummary, PsbcTransaction,
    )
    from src.contracts.models import CompareTask, DiffRecord
    
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
