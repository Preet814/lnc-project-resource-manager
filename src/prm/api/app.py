"""FastAPI application factory."""

from fastapi import FastAPI

from prm.api.exception_handlers import register_exception_handlers
from prm.api.routes import admin_employees, admin_users, auth, health
from prm.api.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(admin_employees.router)
    return app
