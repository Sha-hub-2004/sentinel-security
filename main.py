from fastapi import FastAPI
from app.api.ingest import router as ingest_router
from app.api.publish import router as publish_router
from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.db.session import init_db
from app.services.rabbitmq import init_rabbit, close_rabbit


def create_app() -> FastAPI:
    app = FastAPI(title="Autonomous Security Monitoring - API")
    app.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
    app.include_router(publish_router, prefix="/publish", tags=["publish"])
    app.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """Standard health check endpoint for load balancers and container probes."""
        return {"status": "healthy"}


    @app.on_event("startup")
    async def startup_event() -> None:
        # Initialize DB (create tables). Lightweight for dev.
        await init_db()
        # Initialize RabbitMQ connection (async)
        await init_rabbit()

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        # Close RabbitMQ connections
        await close_rabbit()
        # Close Elasticsearch connections
        from app.services.elasticsearch_client import close_es
        await close_es()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
