def test_new_project_creates_primary_conversation_and_session(test_db):
    from app.models.project import Project
    from app.services.auth_service import register_user
    from app.services.project_service import create_project

    session = register_user(test_db, "project-creator", "password123")
    project = create_project(test_db, name="雨夜归来", user_id=session["user"]["user_id"])

    assert project["name"] == "雨夜归来"
    assert project["primary_conversation_id"] is not None
    assert project["active_session_id"] is not None

    saved = test_db.get(Project, project["project_id"])
    assert saved is not None
    assert saved.user_id == session["user"]["user_id"]
    assert saved.name == "雨夜归来"
    assert saved.stage == "empty"

