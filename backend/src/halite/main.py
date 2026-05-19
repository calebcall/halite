from fastapi import FastAPI

from halite.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Halite", version="0.1.0")
    app.include_router(health_router)
    return app


app = create_app()
