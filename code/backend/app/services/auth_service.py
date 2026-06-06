import base64
import binascii
import hashlib
import hmac
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import AuthSession, User
from app.services.store import now_utc

PASSWORD_ITERATIONS = 200_000


class DuplicateLoginIdError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


def normalize_login_id(login_id: str) -> str:
    return login_id.strip().lower()


def user_to_dict(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "login_id": user.login_id,
        "created_at": user.created_at,
    }


def create_user_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            session_id=f"sess_{uuid.uuid4().hex}",
            user_id=user.user_id,
            token_hash=hash_token(token),
            created_at=now_utc(),
        )
    )
    return token


def register_user(db: Session, login_id: str, password: str) -> dict:
    normalized_login_id = normalize_login_id(login_id)
    if not normalized_login_id or not password:
        raise ValueError("login_id and password are required")

    password_salt, password_hash = hash_password(password)
    user = User(
        user_id=f"user_{uuid.uuid4().hex}",
        login_id=normalized_login_id,
        password_hash=password_hash,
        password_salt=password_salt,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(user)
    try:
        db.flush()
        token = create_user_session(db, user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateLoginIdError(normalized_login_id) from exc
    return {"token": token, "user": user_to_dict(user)}


def login_user(db: Session, login_id: str, password: str) -> dict:
    normalized_login_id = normalize_login_id(login_id)
    user = db.query(User).filter(User.login_id == normalized_login_id).one_or_none()
    if user is None or not verify_password(password, user.password_salt, user.password_hash):
        raise InvalidCredentialsError(normalized_login_id)
    token = create_user_session(db, user)
    db.commit()
    return {"token": token, "user": user_to_dict(user)}


def get_user_by_token(db: Session, token: str) -> User | None:
    token_hash = hash_token(token)
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_hash).one_or_none()
    if session is None:
        return None
    return session.user


def hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")


def verify_password(password: str, password_salt: str, password_hash: str) -> bool:
    try:
        salt = base64.b64decode(password_salt.encode("ascii"))
        expected = base64.b64decode(password_hash.encode("ascii"))
    except (binascii.Error, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
