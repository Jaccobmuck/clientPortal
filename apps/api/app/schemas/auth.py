from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthUserData(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None


class AuthTokenData(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: AuthUserData


class AuthUser(BaseModel):
    user_id: UUID
    email: str | None = None
