from dataclasses import dataclass, field

from app.domain.runs import RunStatus
from app.models.runtime import AgentRun, AgentRunStep
from app.services.store import STORE, now_utc, persistent_id


@dataclass
class BudgetResult:
    allowed: bool
    reason: str | None = None


@dataclass
class RunStep:
    run_step_id: str
    run_id: str
    step_type: str
    status: str = "queued"
    summary: str = ""


@dataclass
class Run:
    run_id: str
    trigger_type: str
    llm_limit: int = 0
    llm_used: int = 0
    steps: list[RunStep] = field(default_factory=list)


_local_run_counter = 0
_local_step_counter = 0


def _next_local(prefix: str) -> str:
    global _local_run_counter, _local_step_counter
    if prefix == "run":
        _local_run_counter += 1
        return f"run_local_{_local_run_counter:03d}"
    _local_step_counter += 1
    return f"step_local_{_local_step_counter:03d}"


def create_run(trigger_type: str, llm_limit: int = 0) -> Run:
    return Run(run_id=_next_local("run"), trigger_type=trigger_type, llm_limit=llm_limit)


def add_run_step(run: Run, step_type: str, status: str = "queued", summary: str = "") -> RunStep:
    step = RunStep(
        run_step_id=_next_local("step"),
        run_id=run.run_id,
        step_type=step_type,
        status=status,
        summary=summary,
    )
    run.steps.append(step)
    return step


def consume_llm_call(run: Run, step_type: str) -> BudgetResult:
    if run.llm_limit and run.llm_used >= run.llm_limit:
        return BudgetResult(allowed=False, reason="llm_budget_exceeded")
    run.llm_used += 1
    return BudgetResult(allowed=True)


def _run_to_dict(run: AgentRun) -> dict:
    steps = sorted(run.steps, key=lambda step: step.order)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "stage": run.stage,
        "current_step": run.current_step,
        "steps": [
            {
                "run_step_id": step.run_step_id,
                "step_type": step.step_type,
                "status": step.status,
                "summary": step.summary,
            }
            for step in steps
        ],
        "failure_message": run.failure_message,
        "project_id": run.project_id,
        "trigger_type": run.trigger_type,
        "created_at": run.created_at,
    }


def create_project_run(project_id: str, trigger_type: str, stage: str, steps: list[str], db=None) -> dict:
    if db is not None:
        timestamp = now_utc()
        run = AgentRun(
            run_id=persistent_id("run"),
            project_id=project_id,
            trigger_type=trigger_type,
            stage=stage,
            status=RunStatus.queued,
            current_step=None,
            failure_message=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
        run.steps = [
            AgentRunStep(
                run_step_id=persistent_id("step"),
                run_id=run.run_id,
                project_id=project_id,
                step_type=step,
                status=RunStatus.queued,
                summary="",
                order=index,
                created_at=timestamp,
                updated_at=timestamp,
            )
            for index, step in enumerate(steps, start=1)
        ]
        db.add(run)
        db.commit()
        db.refresh(run)
        return _run_to_dict(run)

    run_id = STORE.next_id("run")
    run_steps = [
        {
            "run_step_id": STORE.next_id("step"),
            "step_type": step,
            "status": RunStatus.queued,
            "summary": "",
        }
        for step in steps
    ]
    run = {
        "run_id": run_id,
        "status": RunStatus.queued,
        "stage": stage,
        "current_step": None,
        "steps": run_steps,
        "failure_message": None,
        "project_id": project_id,
        "trigger_type": trigger_type,
        "created_at": now_utc(),
    }
    STORE.runs[run_id] = run
    STORE.active_run_by_project[project_id] = run_id
    return run


def update_run_step(project_id: str, run_id: str, step_type: str, status: str, summary: str = "", db=None) -> None:
    if db is not None:
        run = db.get(AgentRun, run_id)
        if run is None or run.project_id != project_id:
            return
        for step in run.steps:
            if step.step_type == step_type:
                step.status = status
                step.summary = summary
                step.updated_at = now_utc()
                break
        if status == RunStatus.running:
            run.current_step = step_type
        run.updated_at = now_utc()
        db.commit()
        return

    run = STORE.runs.get(run_id)
    if run is None:
        return
    for step in run["steps"]:
        if step["step_type"] == step_type:
            step["status"] = status
            step["summary"] = summary
            break
    if status == RunStatus.running:
        run["current_step"] = step_type


def update_run_status(run_id: str, status: str, failure_message: str | None = None, db=None) -> None:
    if db is not None:
        run = db.get(AgentRun, run_id)
        if run is None:
            return
        run.status = status
        run.failure_message = failure_message
        run.updated_at = now_utc()
        if status in (RunStatus.succeeded, RunStatus.failed):
            run.current_step = None
        db.commit()
        return

    run = STORE.runs.get(run_id)
    if run is None:
        return
    run["status"] = status
    run["failure_message"] = failure_message
    if status in (RunStatus.succeeded, RunStatus.failed):
        run["current_step"] = None


def clear_active_run(project_id: str, db=None) -> None:
    if db is not None:
        active = (
            db.query(AgentRun)
            .filter(AgentRun.project_id == project_id, AgentRun.status.in_([RunStatus.queued, RunStatus.running]))
            .all()
        )
        for run in active:
            run.status = RunStatus.failed
            run.failure_message = "Run was cleared"
            run.current_step = None
            run.updated_at = now_utc()
        db.commit()
        return
    STORE.active_run_by_project.pop(project_id, None)


def get_run(project_id: str, run_id: str, db=None) -> dict | None:
    if db is not None:
        run = db.get(AgentRun, run_id)
        if run is not None and run.project_id == project_id:
            return _run_to_dict(run)
        return None

    run = STORE.runs.get(run_id)
    if run and run["project_id"] == project_id:
        return run
    return None


def get_active_run(project_id: str, db=None) -> dict | None:
    if db is not None:
        run = (
            db.query(AgentRun)
            .filter(AgentRun.project_id == project_id, AgentRun.status.in_([RunStatus.queued, RunStatus.running]))
            .order_by(AgentRun.created_at.desc())
            .first()
        )
        return _run_to_dict(run) if run is not None else None

    run_id = STORE.active_run_by_project.get(project_id)
    return STORE.runs.get(run_id) if run_id else None

