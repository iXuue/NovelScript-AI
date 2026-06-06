from app.services.auth_service import create_user, verify_password


def test_register_login_and_me(unauth_client):
    registered = unauth_client.post(
        "/auth/register",
        json={"login_id": "WriterOne", "password": "password123"},
    )
    assert registered.status_code == 200
    payload = registered.json()
    assert payload["token"]
    assert payload["user"]["login_id"] == "writerone"
    assert "password" not in payload["user"]

    duplicate = unauth_client.post(
        "/auth/register",
        json={"login_id": "writerone", "password": "password123"},
    )
    assert duplicate.status_code == 409

    login = unauth_client.post(
        "/auth/login",
        json={"login_id": "WRITERONE", "password": "password123"},
    )
    assert login.status_code == 200
    login_payload = login.json()
    assert login_payload["token"]
    assert login_payload["user"]["user_id"] == payload["user"]["user_id"]

    wrong_password = unauth_client.post(
        "/auth/login",
        json={"login_id": "writerone", "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401

    me = unauth_client.get("/auth/me", headers={"Authorization": f"Bearer {login_payload['token']}"})
    assert me.status_code == 200
    assert me.json()["login_id"] == "writerone"


def test_password_is_hashed_in_database(test_db):
    user = create_user(test_db, "hash-check", "password123")

    assert user.password_hash != "password123"
    assert user.password_salt
    assert verify_password("password123", user) is True
    assert verify_password("wrong-password", user) is False


def test_project_apis_require_authentication(client):
    response = client.get("/projects", headers={"Authorization": ""})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_projects_are_isolated_by_user(client):
    project = client.post("/projects", json={"name": "用户一项目"}).json()
    project_id = project["project_id"]

    second = client.post(
        "/auth/register",
        json={"login_id": "other-user", "password": "password123"},
    ).json()
    second_headers = {"Authorization": f"Bearer {second['token']}"}

    assert client.get("/projects").json()[0]["project_id"] == project_id
    assert client.get("/projects", headers=second_headers).json() == []
    assert client.get(f"/projects/{project_id}", headers=second_headers).status_code == 404
    assert client.get(f"/projects/{project_id}/style-source", headers=second_headers).status_code == 404
