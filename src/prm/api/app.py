"""FastAPI application factory."""

from fastapi import FastAPI

from prm.api.routes import health
from prm.api.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.include_router(health.router)
    return app
