"""Admin user-management API request and response schemas."""

from pydantic import BaseModel, Field

from prm.domain.enums import Role, UserAccountStatus


class CreateUserRequest(BaseModel):
    full_name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    username: str = Field(min_length=1)
    temporary_password: str = Field(min_length=1)
    role: Role
    department: str | None = None
    designation: str | None = None


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1)
    temporary_password: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    full_name: str
    username: str
    email: str
    role: Role
    account_status: UserAccountStatus
    force_password_change: bool


class UserSummaryResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: Role
    account_status: UserAccountStatus
    department: str | None = None
    designation: str | None = None


class UserListResponse(BaseModel):
    users: list[UserSummaryResponse]
    total: int
    active_count: int
    inactive_count: int
