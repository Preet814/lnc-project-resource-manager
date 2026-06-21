"""Auth API request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from prm.domain.enums import Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)
    confirm_password: str = Field(min_length=1)


class VerifyEmailConfirmRequest(BaseModel):
    otp: str = Field(min_length=4, max_length=12)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str
    full_name: str
    role: Role
    force_password_change: bool
    email_verified: bool
    expires_at: datetime
