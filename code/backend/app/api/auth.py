from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.errors import api_error
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import authenticate_user, create_user, issue_token, user_for_token, user_to_public_dict

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    login_id: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=256)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise api_error(401, "not_authenticated", "Authentication required")

    token = authorization[7:].strip()
    if not token:
        raise api_error(401, "not_authenticated", "Authentication required")

    user = user_for_token(db, token)
    if user is None:
        raise api_error(401, "invalid_token", "Invalid authentication token")
    return user


def _auth_response(user: User, token: str) -> dict:
    return {"token": token, "user": user_to_public_dict(user)}


@router.post("/register")
def register_endpoint(payload: AuthRequest, db: Session = Depends(get_db)):
    try:
        user = create_user(db, payload.login_id, payload.password)
    except ValueError:
        raise api_error(409, "login_id_exists", "Login ID already exists")
    token = issue_token(db, user)
    return _auth_response(user, token)


@router.post("/login")
def login_endpoint(payload: AuthRequest, db: Session = Depends(get_db)):
    try:
        user, token = authenticate_user(db, payload.login_id, payload.password)
    except PermissionError:
        raise api_error(401, "invalid_credentials", "Invalid login ID or password")
    return _auth_response(user, token)


@router.get("/me")
def me_endpoint(user: User = Depends(get_current_user)):
    return user_to_public_dict(user)
