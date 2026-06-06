import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.models.user import AuthSession, User
from app.services.auth_service import hash_password, hash_token
from app.services.store import now_utc


def _register(client, login_id: str, password: str = "password123") -> dict:
    response = client.post("/auth/register", json={"login_id": login_id, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_register_login_and_me(unauth_client):
    registered = _register(unauth_client, "Author")

    assert registered["token"]
    assert registered["user"]["login_id"] == "author"
    assert registered["user"]["user_id"].startswith("user_")

    logged_in = unauth_client.post("/auth/login", json={"login_id": "author", "password": "password123"})
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["user_id"] == registered["user"]["user_id"]

    me = unauth_client.get("/auth/me", headers={"Authorization": f"Bearer {registered['token']}"})
    assert me.status_code == 200
    assert me.json()["user_id"] == registered["user"]["user_id"]


def test_duplicate_login_and_wrong_password_return_errors(unauth_client):
    _register(unauth_client, "author")

    duplicate = unauth_client.post("/auth/register", json={"login_id": "AUTHOR", "password": "password123"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "login_id_exists"

    wrong_password = unauth_client.post("/auth/login", json={"login_id": "author", "password": "wrong"})
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"


def test_register_accepts_chinese_english_digits_and_rejects_symbols(unauth_client):
    registered = _register(unauth_client, "作者123")
    assert registered["user"]["login_id"] == "作者123"
    assert registered["user"]["user_id"] != registered["user"]["login_id"]

    invalid_login = unauth_client.post("/auth/register", json={"login_id": "author-a", "password": "password123"})
    assert invalid_login.status_code == 400
    assert invalid_login.json()["error"]["code"] == "invalid_login_id"

    invalid_password = unauth_client.post("/auth/register", json={"login_id": "author2", "password": "12345"})
    assert invalid_password.status_code == 400
    assert invalid_password.json()["error"]["code"] == "invalid_password"


def test_logout_revokes_current_token(unauth_client):
    registered = _register(unauth_client, "logoutuser")
    headers = {"Authorization": f"Bearer {registered['token']}"}

    logout = unauth_client.post("/auth/logout", headers=headers)
    assert logout.status_code == 204

    me = unauth_client.get("/auth/me", headers=headers)
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "invalid_token"


def test_passwords_and_tokens_are_hashed_and_unique_constraints_hold(unauth_client):
    session = _register(unauth_client, "author")

    db_gen = unauth_client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        user = db.query(User).filter(User.login_id == "author").one()
        auth_session = db.query(AuthSession).filter(AuthSession.user_id == user.user_id).one()

        assert user.password_hash != "password123"
        assert user.password_salt != "password123"
        assert auth_session.token_hash == hash_token(session["token"])
        assert auth_session.token_hash != session["token"]
        user_id = user.user_id
        login_id = user.login_id
        token_hash = auth_session.token_hash
        db.expunge(user)

        password_salt, password_hash = hash_password("password123")
        db.add(
            User(
                user_id=user_id,
                login_id="anotherauthor",
                password_hash=password_hash,
                password_salt=password_salt,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            User(
                user_id="user_duplicate_login",
                login_id=login_id,
                password_hash=password_hash,
                password_salt=password_salt,
                created_at=now_utc(),
                updated_at=now_utc(),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        db.add(
            AuthSession(
                session_id="sess_duplicate_token",
                user_id=user_id,
                token_hash=token_hash,
                created_at=now_utc(),
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db_gen.close()


def test_projects_are_isolated_by_user_and_require_auth(unauth_client):
    author_a = _register(unauth_client, "authora")
    author_b = _register(unauth_client, "authorb")
    headers_a = {"Authorization": f"Bearer {author_a['token']}"}
    headers_b = {"Authorization": f"Bearer {author_b['token']}"}

    unauthorized = unauth_client.get("/projects")
    assert unauthorized.status_code == 401

    created = unauth_client.post("/projects", json={"name": "Project A"}, headers=headers_a)
    assert created.status_code == 200
    project = created.json()
    assert project["user_id"] == author_a["user"]["user_id"]

    projects_a = unauth_client.get("/projects", headers=headers_a)
    assert projects_a.status_code == 200
    assert [item["project_id"] for item in projects_a.json()] == [project["project_id"]]

    projects_b = unauth_client.get("/projects", headers=headers_b)
    assert projects_b.status_code == 200
    assert projects_b.json() == []

    forbidden_detail = unauth_client.get(f"/projects/{project['project_id']}", headers=headers_b)
    assert forbidden_detail.status_code == 404

    forbidden_upload = unauth_client.get(f"/projects/{project['project_id']}/chapters/pending", headers=headers_b)
    assert forbidden_upload.status_code == 404
