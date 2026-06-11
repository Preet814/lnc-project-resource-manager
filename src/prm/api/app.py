"""FastAPI application factory."""

from fastapi import FastAPI

from prm.api.exception_handlers import register_exception_handlers
from prm.api.routes import (
    admin_allocations,
    admin_config,
    admin_employees,
    admin_projects,
    admin_users,
    auth,
    engineer,
    health,
    manager,
)
from prm.api.settings import get_settings
from prm.scheduler.lifespan import scheduler_lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=scheduler_lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(admin_users.router)
    app.include_router(admin_employees.router)
    app.include_router(admin_projects.router)
    app.include_router(admin_allocations.router)
    app.include_router(admin_config.router)
    app.include_router(manager.router)
    app.include_router(engineer.router)
    return app
