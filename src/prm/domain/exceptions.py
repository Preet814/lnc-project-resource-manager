"""Domain-level exceptions raised at service boundaries (fail fast)."""


class DomainError(Exception):
    """Base class for predictable business-rule failures."""


class ValidationError(DomainError):
    """Input or state violates a business rule."""


class UnauthorizedError(DomainError):
    """Caller lacks permission for the requested action."""


class NotFoundError(DomainError):
    """Requested entity does not exist."""


class AuthenticationError(DomainError):
    """Invalid credentials or expired session."""


class ConflictError(DomainError):
    """Request conflicts with current state (e.g. over-allocation)."""
