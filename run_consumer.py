import asyncio
from dotenv import load_dotenv

# Load environmental variables from .env if present
load_dotenv()

from app.services.consumer import start_consumer

if __name__ == "__main__":
    try:
        asyncio.run(start_consumer())
    except KeyboardInterrupt:
        print("\n[Consumer] Stopped by user keyboard interrupt. Exiting cleanly.")
