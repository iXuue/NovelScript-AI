import hashlib
import hmac
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.user import AuthSession, User
from app.services.store import now_utc

PASSWORD_HASH_ITERATIONS = 210_000


def normalize_login_id(login_id: str) -> str:
    return login_id.strip().lower()


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(db: Session, login_id: str, password: str) -> User:
    normalized = normalize_login_id(login_id)
    existing = db.query(User).filter(User.login_id == normalized).one_or_none()
    if existing is not None:
        raise ValueError("login_id_exists")

    now = now_utc()
    salt = secrets.token_hex(16)
    user = User(
        user_id=f"user_{uuid4().hex}",
        login_id=normalized,
        password_hash=hash_password(password, salt),
        password_salt=salt,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def verify_password(password: str, user: User) -> bool:
    candidate = hash_password(password, user.password_salt)
    return hmac.compare_digest(candidate, user.password_hash)


def issue_token(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        session_id=f"auth_{uuid4().hex}",
        user_id=user.user_id,
        token_hash=hash_token(token),
        created_at=now_utc(),
    )
    db.add(session)
    db.commit()
    return token


def authenticate_user(db: Session, login_id: str, password: str) -> tuple[User, str]:
    normalized = normalize_login_id(login_id)
    user = db.query(User).filter(User.login_id == normalized).one_or_none()
    if user is None or not verify_password(password, user):
        raise PermissionError("invalid_credentials")
    token = issue_token(db, user)
    return user, token


def user_for_token(db: Session, token: str) -> User | None:
    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_token(token)).one_or_none()
    if session is None:
        return None
    return db.get(User, session.user_id)


def user_to_public_dict(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "login_id": user.login_id,
        "created_at": user.created_at,
    }
