# Autonomous Security Monitoring - FastAPI Backend (Phase 1)

Quick scaffold for the FastAPI backend that ingests API health checks and queue metrics.

Run locally

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

2. Start the app:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Notes
- Uses SQLite by default (see `.env.example`) for quick local dev. Replace with Postgres in production.
- RabbitMQ publish is a placeholder; replace with `aio-pika` or other client in Phase 1/2.
