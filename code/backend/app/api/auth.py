from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import (
    DuplicateLoginIdError,
    InvalidCredentialsError,
    InvalidLoginIdError,
    InvalidPasswordError,
    get_user_by_token,
    login_user,
    register_user,
    revoke_token,
    user_to_dict,
)

router = APIRouter()


class RegisterRequest(BaseModel):
    login_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/auth/register")
def register_endpoint(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        return register_user(db, payload.login_id, payload.password)
    except InvalidLoginIdError as exc:
        raise api_error(400, "invalid_login_id", str(exc))
    except InvalidPasswordError as exc:
        raise api_error(400, "invalid_password", str(exc))
    except DuplicateLoginIdError:
        raise api_error(409, "login_id_exists", "Login ID already exists")
    except ValueError as exc:
        raise api_error(400, "validation_error", str(exc))


@router.post("/auth/login")
def login_endpoint(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        return login_user(db, payload.login_id, payload.password)
    except InvalidCredentialsError:
        raise api_error(401, "invalid_credentials", "Invalid login ID or password")


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if authorization is None:
        raise api_error(401, "not_authenticated", "Authentication is required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise api_error(401, "invalid_token", "Invalid authentication token")
    user = get_user_by_token(db, token.strip())
    if user is None:
        raise api_error(401, "invalid_token", "Invalid authentication token")
    return user


@router.get("/auth/me")
def me_endpoint(current_user: User = Depends(get_current_user)):
    return user_to_dict(current_user)


@router.post("/auth/logout", status_code=204)
def logout_endpoint(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if authorization is None:
        return Response(status_code=204)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        revoke_token(db, token.strip())
    return Response(status_code=204)
