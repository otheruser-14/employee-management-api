from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.v1.dependencies import DbSession, get_current_user
from app.models import User
from app.schemas.auth import AuthenticatedUser, LoginRequest, TokenResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, db: DbSession) -> TokenResponse:
    try:
        access_token = auth_service.login(
            db,
            str(credentials.email),
            credentials.password.get_secret_value(),
        )
    except (auth_service.InvalidCredentialsError, auth_service.InactiveUserError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=AuthenticatedUser)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
