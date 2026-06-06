from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from app.core.config import settings


db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine: AsyncEngine = create_async_engine(db_url, echo=False, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)



async def init_db() -> None:
    async with engine.begin() as conn:
        # Create tables if they do not exist
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed default Admin user if not present
    from sqlmodel import select
    from app.models import User
    from app.core.security import get_password_hash

    async with async_session() as session:
        stmt = select(User).where(User.username == "admin")
        res = await session.execute(stmt)
        admin = res.scalars().first()
        if not admin:
            hashed_pw = get_password_hash("admin123")
            admin_user = User(
                username="admin",
                hashed_password=hashed_pw,
                role="Admin"
            )
            session.add(admin_user)
            await session.commit()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
