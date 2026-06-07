"""Map domain exceptions to HTTP responses (fail fast at API boundary)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from prm.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    LlmUnavailableError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        _request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        _request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_error_handler(
        _request: Request, exc: UnauthorizedError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(LlmUnavailableError)
    async def llm_unavailable_error_handler(
        _request: Request, exc: LlmUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
