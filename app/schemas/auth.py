from pydantic import BaseModel, EmailStr, Field, SecretStr

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthenticatedUser(BaseModel):
    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    employee_id: int | None
