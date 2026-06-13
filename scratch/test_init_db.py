import asyncio
from dotenv import load_dotenv

# Load environmental variables from .env
load_dotenv()

from app.db.session import init_db

async def test_init():
    try:
        print("Running database initialization against Supabase...")
        await init_db()
        print("Success! Database schema initialized and seeded successfully.")
    except Exception as exc:
        print("Database initialization failed!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_init())
