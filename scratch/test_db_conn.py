import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def test_conn():
    # Replace +asyncpg and try connecting
    db_url = "postgresql+asyncpg://postgres.yeofslokuwlorecuvyvv:FahadDB2026SecureX9K7M4P2@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres"
    print("Testing connection to:", db_url.split("@")[-1])
    try:
        engine = create_async_engine(db_url, echo=True)
        async with engine.begin() as conn:
            print("Successfully connected to Supabase!")
            # Run simple query
            result = await conn.execute("SELECT 1")
            print("Query Result:", result.scalar())
    except Exception as exc:
        print("Database connection failed!")
        print("Error details:", exc)

if __name__ == "__main__":
    asyncio.run(test_conn())
