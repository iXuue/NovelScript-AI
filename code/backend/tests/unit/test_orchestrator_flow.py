import pytest

from app.services import orchestrator_service
from app.services.orchestrator_service import build_initial_generation_plan


def test_initial_generation_order():
    plan = build_initial_generation_plan()
    assert set(plan.parallel_groups[0]) == {"chapter_summary", "style_profile"}
    assert plan.dependencies["scene_plan"] == ["chapter_summary", "style_profile"]


def test_script_generation_rolls_back_before_failure_updates(monkeypatch):
    class SessionStub:
        def __init__(self):
            self.rollback_count = 0

        def rollback(self):
            self.rollback_count += 1

    session = SessionStub()
    events = []

    def fail_generation(db, project_id, llm_provider, run_id=None):
        raise RuntimeError("database write failed")

    monkeypatch.setattr(
        orchestrator_service,
        "create_project_run",
        lambda *args, **kwargs: {"run_id": "run_test"},
    )
    monkeypatch.setattr(orchestrator_service, "generate_script_from_confirmed_scene_plan", fail_generation)
    monkeypatch.setattr(
        orchestrator_service,
        "update_run_step",
        lambda project_id, run_id, step_type, status, summary="", db=None: events.append(
            ("step", status, summary, session.rollback_count)
        ),
    )
    monkeypatch.setattr(
        orchestrator_service,
        "update_run_status",
        lambda run_id, status, failure_message=None, db=None: events.append(
            ("status", status, failure_message, session.rollback_count)
        ),
    )
    monkeypatch.setattr(
        orchestrator_service,
        "mirror_project_snapshot",
        lambda db, project_id: events.append(("snapshot", session.rollback_count)),
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        orchestrator_service.generate_script("proj_test", db=session)

    assert session.rollback_count == 1
    assert ("step", "failed", "database write failed", 1) in events
    assert ("status", "failed", "database write failed", 1) in events
    assert events[-1] == ("snapshot", 1)
