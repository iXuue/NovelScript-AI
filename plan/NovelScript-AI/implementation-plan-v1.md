# NovelScript AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the NovelScript AI MVP: a Python + Docker + PostgreSQL application that converts 3-5 novel chapters into traceable, validated, read-only YAML-preview script drafts with conversation-based revision.

**Architecture:** The backend is a FastAPI service with explicit domain modules for projects, files, artifacts, schemas, runs, workers, orchestration, export, and developer logs. PostgreSQL is the business source of truth; the filesystem stores raw uploads, exports, and local developer debug snapshots only. The frontend is a single three-column React workspace that shows project navigation, a Codex-like conversation area, and right-side Scene Plan / read-only YAML preview.

**Tech Stack:** Confirmed stack: Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic, PyYAML, python-docx, pypdf, pytest, Docker Compose, React + TypeScript + Vite + Vitest.

---

## Source Requirement

- Requirement document: `E:/七牛云/spec/NovelScript-AI/requirements-v1.md`
- Plan location: `E:/七牛云/plan/NovelScript-AI/implementation-plan-v1.md`
- Proposed code root for implementation: `E:/七牛云/code/NovelScript-AI`
- Confirmed implementation choices: FastAPI backend, React + Vite frontend, SQLAlchemy + Alembic persistence, Docker Compose local environment.

Execution gate: before creating or modifying code files, confirm with the user that `E:/七牛云/code/NovelScript-AI` is the approved code boundary. This plan itself does not create application code.

Execution versioning rule: after the code root is confirmed and a Git repository is available, each task must end with its verification command and a commit. If Git is unavailable or repository ownership blocks commits, stop execution and report that condition before continuing.

```powershell
git -C E:\七牛云\code\NovelScript-AI status
git -C E:\七牛云\code\NovelScript-AI add -A -- .
git -C E:\七牛云\code\NovelScript-AI commit -m "feat: add current task implementation"
```

Recommended task-scoped commit messages:

```text
feat: bootstrap backend and docker environment
feat: add domain contracts and schemas
feat: add postgres models and migrations
feat: add input adapter and chapter confirmation
feat: add style source and style reference upload
feat: add run budgets and developer logs
feat: add orchestrator workers and prompt memory
feat: add scene plan confirmation and invalidation
feat: add script generation validation and repair
feat: add export service
feat: add backend api integration flow
feat: add frontend workspace
test: add end-to-end acceptance checks
```

## MVP Scope

Implement:

- Project creation with one primary conversation and one active session.
- Upload and normalize `.md`, `.txt`, `.doc`, `.docx`, and text PDF into Markdown.
- Chapter confirmation panel and stable paragraph IDs.
- Chapter summaries, evidence index, Story Bible, Style Profile, Scene Plan, script JSON, traceability index.
- Three mutually exclusive style sources: built-in style, user style text, uploaded historical script.
- Explicit Scene Plan confirmation before script generation.
- Internal JSON as authority, read-only YAML preview for users.
- Validation Agent + programmatic validators.
- `run_id` and `run_step_id` logging with local developer logs only.
- Budget tracking for project/session, run, scene, LLM calls, and tool calls.
- Artifact invalidation with `current`, `stale`, `historical`, `failed`.
- Export to YAML, Markdown, DOCX, DOC, PDF, TXT, and user clean JSON.
- Frontend three-column workspace and source evidence modal.

Do not implement:

- OCR for scanned PDFs.
- User editing YAML directly.
- User editing Scene Plan fields directly.
- Version rollback.
- Frontend developer mode or run log viewer.
- Frontend artificial manual review workflow.

## File Structure

Create this structure under `E:/七牛云/code/NovelScript-AI`:

```text
E:/七牛云/code/NovelScript-AI/
  backend/
    app/
      main.py
      core/config.py
      core/database.py
      core/paths.py
      domain/artifacts.py
      domain/budgets.py
      domain/checkpoints.py
      domain/conversations.py
      domain/evidence.py
      domain/memory.py
      domain/projects.py
      domain/runs.py
      domain/schemas.py
      domain/scripts.py
      domain/style.py
      domain/traceability.py
      services/input_adapter.py
      services/chapter_service.py
      services/project_service.py
      services/conversation_service.py
      services/style_service.py
      services/artifact_service.py
      services/run_service.py
      services/checkpoint_service.py
      services/memory_service.py
      services/prompt_package_service.py
      services/llm_provider.py
      services/worker_service.py
      services/orchestrator_service.py
      services/validation_service.py
      services/export_service.py
      services/developer_log_service.py
      services/evidence_service.py
      api/projects.py
      api/uploads.py
      api/style_uploads.py
      api/style_source.py
      api/runs.py
      api/conversations.py
      api/scene_plan.py
      api/scripts.py
      api/exports.py
      api/evidence.py
    migrations/
      env.py
      versions/
    tests/
      conftest.py
      unit/
      integration/
    Dockerfile
    alembic.ini
    pyproject.toml
  frontend/
    src/
      api/client.ts
      app/App.tsx
      components/ProjectSidebar.tsx
      components/ConversationPane.tsx
      components/StyleSourceSelector.tsx
      components/AgentProgress.tsx
      components/ResultPane.tsx
      components/EvidenceModal.tsx
      components/YamlPreview.tsx
      state/projectStore.ts
      types.ts
    tests/
    Dockerfile
    package.json
    tsconfig.json
    vite.config.ts
    vitest.setup.ts
  docker-compose.yml
  README.md
```

Boundary rules:

- `backend/app/domain/*` defines data contracts and enums only.
- `backend/app/services/*` owns business logic.
- `backend/app/api/*` only translates HTTP requests/responses.
- `frontend/src/components/*` contains UI components with no business rules beyond display state.
- Database reads are the default business reads. Filesystem JSON/YAML/JSONL is only raw material, export output, or local developer debug snapshot.

---

## Interface Document

Frontend/backend interface contract is maintained separately:

- `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`

Implementation tasks must follow the interface document. If an endpoint shape changes, update the interface document first, then update affected backend/frontend tasks.

### Task 1: Backend Bootstrap And Configuration

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/main.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/core/config.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/core/database.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/core/paths.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/pyproject.toml`
- Create: `E:/七牛云/code/NovelScript-AI/backend/Dockerfile`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_health.py`
- Create: `E:/七牛云/code/NovelScript-AI/docker-compose.yml`

- [ ] **Step 1: Write the health test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_health.py -q
```

Expected: import or route failure before implementation.

- [ ] **Step 3: Implement minimal FastAPI app**

```python
from fastapi import FastAPI

app = FastAPI(title="NovelScript AI")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Add config and path helpers**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://novelscript:novelscript@postgres:5433/novelscript"
    file_storage_root: str = "/var/lib/novelscript/files"
    developer_runs_root: str = "/var/lib/novelscript/developer_runs"
    local_developer_logs_enabled: bool = True


settings = Settings()
```

- [ ] **Step 5: Add Docker Compose**

Create `backend/pyproject.toml`:

```toml
[project]
name = "novelscript-ai-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "psycopg[binary]>=3.2",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "pyyaml>=6.0",
  "python-docx>=1.1",
  "pypdf>=4.3",
  "python-multipart>=0.0.9",
]

[project.optional-dependencies]
test = [
  "pytest>=8.0",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir ".[test]"

COPY app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
services:
  postgres:
    image: postgres:16
    command: ["postgres", "-c", "port=5433"]
    environment:
      POSTGRES_DB: novelscript
      POSTGRES_USER: novelscript
      POSTGRES_PASSWORD: novelscript
    ports:
      - "5433:5433"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+psycopg://novelscript:novelscript@postgres:5433/novelscript
    depends_on:
      - postgres
    ports:
      - "8000:8000"
    volumes:
      - app_files:/var/lib/novelscript/files
      - developer_runs:/var/lib/novelscript/developer_runs
  frontend:
    build: ./frontend
    depends_on:
      - backend
    ports:
      - "5173:5173"
    environment:
      VITE_API_BASE_URL: http://localhost:8000

volumes:
  postgres_data:
  app_files:
  developer_runs:
```

- [ ] **Step 6: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_health.py -q
```

Expected: `1 passed`.

---

### Task 2: Domain Contracts And Schemas

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/artifacts.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/runs.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/scripts.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/traceability.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/schemas.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_script_schemas.py`

- [ ] **Step 1: Write schema tests**

```python
import pytest
from pydantic import ValidationError

from app.domain.scripts import ContentBlock, InternalScriptScene, UserCleanScript
from app.domain.traceability import TraceabilityIndex


def test_internal_content_block_requires_content_block_id():
    block = ContentBlock(content_block_id="CB001", type="dialogue", speaker="林雨", text="我回来了。")
    assert block.content_block_id == "CB001"


def test_user_clean_script_rejects_internal_trace_fields():
    with pytest.raises(ValidationError):
        UserCleanScript(
            title="雨夜归来",
            characters=[],
            scenes=[],
            content_block_id="CB001",
        )


def test_traceability_maps_content_block_to_evidence():
    index = TraceabilityIndex(
        mappings=[
            {
                "content_block_id": "CB001",
                "scene_id": "S001",
                "source_evidence_id": "EV001",
                "chapter_id": "CH001",
                "paragraph_id": "CH001_P001",
            }
        ]
    )
    assert index.mappings[0].content_block_id == "CB001"
```

- [ ] **Step 2: Implement Pydantic models**

Use these enum values:

```python
from enum import StrEnum


class ArtifactStatus(StrEnum):
    current = "current"
    stale = "stale"
    historical = "historical"
    failed = "failed"


class RunStepType(StrEnum):
    input_conversion = "input_conversion"
    chapter_detection = "chapter_detection"
    paragraph_numbering = "paragraph_numbering"
    chapter_summary = "chapter_summary"
    evidence_extraction = "evidence_extraction"
    story_bible = "story_bible"
    style_profile = "style_profile"
    scene_plan = "scene_plan"
    script_generation = "script_generation"
    validation = "validation"
    repair = "repair"
    export = "export"
```

Define internal script and clean export separation:

```python
from pydantic import BaseModel, ConfigDict, Field


class ContentBlock(BaseModel):
    content_block_id: str
    type: str
    text: str
    speaker: str | None = None
    source_evidence_ids: list[str] = Field(default_factory=list)


class InternalScriptScene(BaseModel):
    scene_id: str
    title: str
    source_chapter_ids: list[str]
    content_blocks: list[ContentBlock]


class UserCleanScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    characters: list[dict]
    scenes: list[dict]
```

- [ ] **Step 3: Run schema tests**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_script_schemas.py -q
```

Expected: all tests pass.

---

### Task 3: Database Models And Migrations

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/core/database.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/projects.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/conversations.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/project_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/artifact_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/alembic.ini`
- Create: `E:/七牛云/code/NovelScript-AI/backend/migrations/env.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/conftest.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/integration/test_project_creation.py`

- [ ] **Step 1: Write project creation integration test**

```python
def test_new_project_creates_primary_conversation_and_session(test_db):
    from app.services.project_service import create_project

    project = create_project(test_db, name="雨夜归来")

    assert project.name == "雨夜归来"
    assert project.primary_conversation_id is not None
    assert project.active_session_id is not None
```

- [ ] **Step 2: Create tables**

Create `tests/conftest.py` with a database fixture:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base


@pytest.fixture()
def test_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

Tables required for MVP:

```text
projects
script_generations
conversations
sessions
messages
files
artifacts
artifact_dependencies
runs
run_steps
checkpoints
exports
```

Critical columns:

```text
artifacts: id, project_id, session_id, artifact_type, status, version, payload_json, created_at
runs: id, project_id, session_id, conversation_id, trigger_type, status, budget_json, created_at
run_steps: id, run_id, step_type, status, llm_call_count, tool_call_count, result_summary, created_at
artifact_dependencies: upstream_artifact_id, downstream_artifact_id, invalidates_on_change
```

Alembic requirements:

```text
alembic.ini points to migrations/env.py.
migrations/env.py imports app.core.database.Base.metadata.
First migration creates all MVP tables and enum-compatible status columns.
Migration is required before Docker smoke test.
```

- [ ] **Step 3: Implement artifact status update**

```python
def mark_downstream_stale(db, upstream_artifact_id: str) -> list[str]:
    downstream_ids = find_downstream_artifacts(db, upstream_artifact_id)
    for artifact_id in downstream_ids:
        update_artifact_status(db, artifact_id, "stale")
    return downstream_ids
```

- [ ] **Step 4: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/integration/test_project_creation.py -q
```

Expected: project, primary conversation, session, and initial checkpoint are created.

---

### Task 4: Input Adapter, Chapter Confirmation, Paragraph IDs

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/input_adapter.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/chapter_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/uploads.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_chapter_service.py`

- [ ] **Step 1: Write chapter detection tests**

```python
from app.services.chapter_service import detect_chapters, assign_paragraph_ids


def test_detect_chinese_chapters():
    markdown = "# 第一章 雨夜\n\n她回来了。\n\n# 第二章 旧信\n\n信封泛黄。"
    chapters = detect_chapters(markdown)
    assert [chapter.title for chapter in chapters] == ["第一章 雨夜", "第二章 旧信"]


def test_assign_stable_paragraph_ids():
    chapters = detect_chapters("# 第一章 雨夜\n\n她回来了。\n\n门开了。")
    indexed = assign_paragraph_ids(chapters)
    assert indexed[0].paragraphs[0].paragraph_id == "CH001_P001"
    assert indexed[0].paragraphs[1].paragraph_id == "CH001_P002"
```

- [ ] **Step 2: Implement conversion support**

Input support:

```text
.md  -> read text
.txt -> read text
.docx -> python-docx paragraph extraction
.doc -> LibreOffice conversion to .docx, then python-docx paragraph extraction
.pdf -> pypdf text extraction only
```

- [ ] **Step 3: Implement chapter confirmation state**

API behavior:

```text
POST /projects/{project_id}/uploads -> stores raw file, normalized markdown, detected chapters
GET /projects/{project_id}/chapters/pending -> returns detected chapter list
POST /projects/{project_id}/chapters/confirm -> confirms chapter order and creates paragraph IDs
```

- [ ] **Step 4: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_chapter_service.py -q
```

Expected: chapter detection and paragraph IDs pass.

---

### Task 5: Style Source And Style Profile

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/style.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/style_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/style_uploads.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/style_source.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_style_source.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/integration/test_style_source_api.py`

- [ ] **Step 1: Write mutual exclusion tests**

```python
import pytest

from app.services.style_service import validate_style_source


def test_builtin_style_is_valid():
    source = validate_style_source({"kind": "builtin", "builtin_style": "suspense"})
    assert source.kind == "builtin"


def test_text_and_file_are_mutually_exclusive():
    with pytest.raises(ValueError):
        validate_style_source({
            "kind": "custom",
            "style_text": "更悬疑，对白短促",
            "reference_file_ids": ["file_1"],
        })
```

- [ ] **Step 2: Implement style source model**

Supported values:

```text
builtin: realism, suspense, romance, comedy, short_drama
custom_text: user style description
reference_scripts: up to 3 uploaded historical scripts
```

- [ ] **Step 3: Write style reference upload API test**

```python
def test_style_reference_upload_does_not_replace_novel_upload(client):
    project = client.post("/projects", json={"name": "雨夜归来"}).json()
    project_id = project["project_id"]

    novel = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章\n\n她回来了。")},
    )
    assert novel.status_code == 200

    style_file = client.post(
        f"/projects/{project_id}/style-reference-uploads",
        files={"file": ("past-script.md", "# 场景一\n\n她：我回来了。")},
    )
    assert style_file.status_code == 200
    assert style_file.json()["purpose"] == "style_reference"

    chapters = client.get(f"/projects/{project_id}/chapters/pending").json()
    assert len(chapters["chapters"]) == 1
```

- [ ] **Step 4: Implement lock rules**

Rules:

```text
Before Scene Plan confirmation: user may clear style source and choose again.
After Scene Plan confirmation: style source is locked.
Post-confirmation style words in chat are ordinary modification instructions.
Post-confirmation style words do not rerun Style Profile Worker.
```

- [ ] **Step 5: Implement style source API behavior**

Rules:

```text
POST /projects/{project_id}/style-reference-uploads stores files with purpose=style_reference.
POST /projects/{project_id}/style-source accepts exactly one of builtin, custom_text, reference_scripts.
GET /projects/{project_id}/style-source returns the selected source or null.
DELETE /projects/{project_id}/style-source clears it only before Scene Plan confirmation.
All style source mutations after Scene Plan confirmation return 409 style_source_locked.
```

- [ ] **Step 6: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_style_source.py tests/integration/test_style_source_api.py -q
```

Expected: mutual exclusion, lock rules, and style reference upload behavior pass.

---

### Task 6: Run, Step, Budget, And Developer Logs

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/budgets.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/run_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/developer_log_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_run_budget.py`

- [ ] **Step 1: Write run budget tests**

```python
from app.services.run_service import create_run, add_run_step, consume_llm_call


def test_auto_repair_is_step_not_new_run():
    run = create_run(trigger_type="script_generation")
    validation_step = add_run_step(run, "validation")
    repair_step = add_run_step(run, "repair")

    assert validation_step.run_id == run.run_id
    assert repair_step.run_id == run.run_id


def test_run_budget_stops_when_limit_reached():
    run = create_run(trigger_type="conversation_edit", llm_limit=1)
    consume_llm_call(run, step_type="conversation_edit")
    result = consume_llm_call(run, step_type="validation")
    assert result.allowed is False
    assert result.reason == "llm_budget_exceeded"
```

- [ ] **Step 2: Implement default budgets**

```python
DEFAULT_PROJECT_BUDGET = {
    "max_chapters": 5,
    "max_total_characters": 50000,
    "max_llm_calls": 120,
    "max_tool_calls": 200,
    "max_active_runs": 1,
}

DEFAULT_RUN_BUDGETS = {
    "initial_analysis_scene_plan": {"llm": 60, "tools": 100},
    "scene_plan_regeneration": {"llm": 12, "tools": 25},
    "script_generation": {"llm": 80, "tools": 120},
    "conversation_edit": {"llm": 6, "tools": 15},
    "validation_rerun": {"llm": 4, "tools": 10},
    "export": {"llm": 0, "tools": 10},
}
```

- [ ] **Step 3: Implement local developer log retention**

Rules:

```text
Logs write only when local_developer_logs_enabled is true.
Keep latest 7 days or latest 50 runs, whichever threshold is reached first.
Project deletion removes local developer logs linked to that project.
Do not write API keys, DB URLs, or system secrets.
```

- [ ] **Step 4: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_run_budget.py -q
```

Expected: run/step and budget behavior pass.

---

### Task 7: Worker Services And Orchestrator

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/domain/memory.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/memory_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/llm_provider.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/worker_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/orchestrator_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/prompt_package_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_memory_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_llm_provider.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_orchestrator_flow.py`

- [ ] **Step 1: Write memory compression tests**

```python
from app.services.memory_service import build_prompt_memory


def test_long_context_uses_summary_without_raw_truncation():
    memory = build_prompt_memory(
        stage="script_generation",
        scope={"scene_id": "S001"},
        chapter_summaries=[{"chapter_id": "CH001", "summary": "女主雨夜回到旧宅。"}],
        evidence_refs=[{"source_evidence_id": "EV001", "paragraph_id": "CH001_P001"}],
        story_bible={"characters": [{"name": "林雨"}]},
        style_profile={"dialogue": "短句，压迫感强"},
        conversation_summary="用户要求节奏更紧张。",
        raw_context_characters=80000,
        max_prompt_characters=12000,
    )

    assert memory.compression_used is True
    assert "chapter_summaries" in memory.layers
    assert "story_bible" in memory.layers
    assert "style_profile" in memory.layers
    assert "conversation_summary" in memory.layers
    assert memory.raw_full_novel_included is False


def test_scene_edit_memory_uses_confirmed_scene_plan_and_scene_evidence():
    memory = build_prompt_memory(
        stage="conversation_edit",
        scope={"scene_id": "S001"},
        confirmed_scene_plan={"scene_id": "S001", "title": "雨夜归来"},
        scene_evidence_refs=[{"source_evidence_id": "EV001", "paragraph_id": "CH001_P001"}],
        conversation_summary="用户要求第一场对白更短。",
        max_prompt_characters=6000,
    )

    assert "confirmed_scene_plan" in memory.layers
    assert "scene_evidence_refs" in memory.layers
    assert memory.scope["scene_id"] == "S001"
```

- [ ] **Step 2: Implement memory package contract**

Memory rules:

```text
Do not hard-crop long source content.
When content exceeds the prompt budget, summarize older or oversized content and store the summary as a business artifact in PostgreSQL.
Keep source evidence references even when raw source text is summarized.
Prompt memory is selected by stage: scene_plan generation, script_generation, and conversation_edit do not receive identical memory packages.
scene_plan memory uses chapter summaries, evidence index, Story Bible, Style Profile, and latest user instruction.
script_generation memory uses confirmed Scene Plan, Story Bible, Style Profile, scene-specific evidence, prior scene summaries, and latest user instruction.
conversation_edit memory uses conversation summary, current script version, confirmed Scene Plan boundary, target scene or chapter, relevant evidence, and latest user instruction.
```

- [ ] **Step 3: Write LLM provider tests**

```python
from app.services.llm_provider import StubLLMProvider, LLMRequest


def test_stub_provider_returns_deterministic_json():
    provider = StubLLMProvider()
    response = provider.generate(LLMRequest(task_type="scene_plan", prompt="make scene plan"))
    assert response.model_name == "stub"
    assert response.text
    assert response.usage.input_tokens >= 0
```

- [ ] **Step 4: Implement LLM provider boundary**

Provider contract:

```python
from dataclasses import dataclass


@dataclass
class LLMUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class LLMRequest:
    task_type: str
    prompt: str
    response_format: str = "json"


@dataclass
class LLMResponse:
    text: str
    model_name: str
    usage: LLMUsage


class LLMProvider:
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError
```

Implementation requirements:

```text
StubLLMProvider is used in unit and integration tests.
ConfiguredLLMProvider is used in development when API credentials are available through environment variables.
ConfiguredLLMProvider never writes API keys, database URLs, or raw secret values to Prompt logs, run_steps, tool_calls, or tool_results.
Worker services depend on LLMProvider interface, not on a concrete model vendor.
Every LLM call writes run_id, run_step_id, task_type, input summary, output summary, and usage.
```

- [ ] **Step 5: Write orchestration order test**

```python
from app.services.orchestrator_service import build_initial_generation_plan


def test_initial_generation_order():
    plan = build_initial_generation_plan()
    assert set(plan.parallel_groups[0]) == {"chapter_summary", "evidence_extraction", "style_profile"}
    assert plan.dependencies["story_bible"] == ["chapter_summary", "evidence_extraction"]
    assert plan.dependencies["scene_plan"] == ["story_bible", "style_profile"]
```

- [ ] **Step 6: Implement worker contracts**

Worker output contracts:

```text
Chapter Summary Worker -> chapter_summaries artifact
Evidence Extraction Worker -> evidence_index artifact
Style Profile Worker -> style_profile artifact
Story Bible Worker -> story_bible artifact
Scene Plan Worker -> scene_plan artifact
Script Generation Worker -> internal_script_scene artifacts
Validation Agent -> validation_report artifact
Programmatic Validators -> validator_report artifact
```

- [ ] **Step 7: Implement prompt injection package**

Each LLM call must include:

```text
current task stage
current task target
current processing scope
latest user instruction
confirmed user decisions
allowed change boundary
relevant memory
relevant evidence
schema constraints
forbidden rules
```

Prompt package rules:

```text
relevant memory must come from memory_service.build_prompt_memory().
Prompt packages must store input summaries and output summaries in run_steps.
Full raw Prompt, tool parameters, tool returns, and model returns may be written only to local developer debug snapshots when local_developer_logs_enabled is true.
No frontend endpoint exposes these developer debug snapshots.
```

- [ ] **Step 8: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_memory_service.py tests/unit/test_llm_provider.py tests/unit/test_orchestrator_flow.py -q
```

Expected: memory packaging, LLM provider boundary, worker ordering, and prompt package contents pass.

---

### Task 8: Scene Plan Confirmation And Artifact Invalidation

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/scene_plan.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/checkpoint_service.py`
- Modify: `E:/七牛云/code/NovelScript-AI/backend/app/services/artifact_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_artifact_invalidation.py`

- [ ] **Step 1: Write invalidation tests**

```python
from app.services.artifact_service import invalidate_after_style_change, invalidate_after_scene_plan_change


def test_style_change_before_confirmation_invalidates_style_and_scene_plan():
    changed = invalidate_after_style_change(scene_plan_confirmed=False)
    assert "style_profile" in changed
    assert "scene_plan" in changed
    assert "script_json" in changed


def test_scene_plan_change_invalidates_script_and_exports():
    changed = invalidate_after_scene_plan_change()
    assert changed == ["script_json", "traceability_index", "yaml_preview", "exports"]
```

- [ ] **Step 2: Implement explicit confirmation**

API behavior:

```text
POST /projects/{project_id}/scene-plan/confirm
Body: {"confirmation_source": "button"} or {"confirmation_source": "conversation", "message_id": "..."}
Effect: save checkpoint, lock style source, mark scene_plan as current, allow script generation after confirmation.
```

- [ ] **Step 3: Implement stale status**

Artifact states:

```text
current
stale
historical
failed
```

Use `stale` whenever upstream inputs change.

- [ ] **Step 4: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_artifact_invalidation.py -q
```

Expected: invalidation and explicit confirmation pass.

---

### Task 9: Script Generation, Validation, Repair

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/validation_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/scripts.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_script_generation.py`

- [ ] **Step 1: Write traceability test**

```python
from app.services.validation_service import validate_traceability


def test_every_content_block_has_traceability_mapping():
    script = {
        "scenes": [{"scene_id": "S001", "content_blocks": [{"content_block_id": "CB001", "text": "她回来了。"}]}]
    }
    traceability = {
        "mappings": [{"content_block_id": "CB001", "scene_id": "S001", "source_evidence_id": "EV001"}]
    }
    result = validate_traceability(script, traceability)
    assert result.valid is True
```

- [ ] **Step 2: Implement per-scene generation flow**

Each scene runs:

```text
generate internal JSON
programmatic schema validation
Validation Agent quality check
repair if allowed by budget
revalidate
save checkpoint
```

- [ ] **Step 3: Implement failure state**

If repair fails:

```text
mark artifact failed
save validation report
keep successful previous artifacts
return user-visible failed stage
do not expose developer logs
```

- [ ] **Step 4: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_script_generation.py -q
```

Expected: traceability and failure state behavior pass.

---

### Task 10: Export Service

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/export_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/exports.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/unit/test_exports.py`

- [ ] **Step 1: Write clean export tests**

```python
from app.services.export_service import to_user_clean_json, to_yaml_preview


def test_clean_json_removes_internal_fields():
    internal = {
        "title": "雨夜归来",
        "characters": [],
        "scenes": [{"scene_id": "S001", "content_blocks": [{"content_block_id": "CB001", "text": "她回来了。"}]}],
    }
    clean = to_user_clean_json(internal)
    assert "content_block_id" not in str(clean)


def test_yaml_preview_matches_clean_json_shape():
    clean = {"title": "雨夜归来", "characters": [], "scenes": []}
    yaml_text = to_yaml_preview(clean)
    assert "title: 雨夜归来" in yaml_text
```

- [ ] **Step 2: Implement supported exports**

Supported export formats:

```text
YAML
Markdown
DOCX
DOC
PDF
TXT
user_clean_json
```

DOC and PDF exports are generated from DOCX through LibreOffice.

- [ ] **Step 3: Implement export run**

Export run rules:

```text
LLM calls: 0
tool calls: maximum 10
export reads current internal JSON from PostgreSQL
export never reads developer debug snapshot as business source
export removes internal trace fields
```

- [ ] **Step 4: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/unit/test_exports.py -q
```

Expected: clean JSON and YAML preview tests pass.

---

### Task 11: Backend API Integration Tests

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/projects.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/style_uploads.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/style_source.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/runs.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/conversations.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/scene_plan.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/scripts.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/exports.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/api/evidence.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/conversation_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/app/services/evidence_service.py`
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/integration/test_mvp_flow.py`

- [ ] **Step 1: Write MVP flow test**

```python
def test_mvp_flow_creates_project_uploads_confirms_scene_plan_and_exports(client):
    project = client.post("/projects", json={"name": "雨夜归来"}).json()
    project_id = project["project_id"]

    upload = client.post(
        f"/projects/{project_id}/uploads",
        files={"file": ("novel.md", "# 第一章 雨夜\n\n她回来了。\n\n# 第二章 旧信\n\n信封泛黄。")},
    )
    assert upload.status_code == 200

    chapters = client.get(f"/projects/{project_id}/chapters/pending").json()
    assert len(chapters["chapters"]) == 2

    confirm = client.post(f"/projects/{project_id}/chapters/confirm", json={"chapter_ids": [c["chapter_id"] for c in chapters["chapters"]]})
    assert confirm.status_code == 200

    style = client.post(f"/projects/{project_id}/style-source", json={"kind": "builtin", "builtin_style": "suspense"})
    assert style.status_code == 200

    scene_plan = client.post(f"/projects/{project_id}/scene-plan/generate")
    assert scene_plan.status_code == 200

    confirm_scene_plan = client.post(f"/projects/{project_id}/scene-plan/confirm", json={"confirmation_source": "button"})
    assert confirm_scene_plan.status_code == 200

    script_run = client.post(f"/projects/{project_id}/scripts/generate")
    assert script_run.status_code == 200

    preview = client.get(f"/projects/{project_id}/scripts/current/yaml-preview")
    assert preview.status_code == 200
    assert "yaml" in preview.json()

    export = client.post(f"/projects/{project_id}/exports", json={"format": "yaml"})
    assert export.status_code == 200
```

- [ ] **Step 2: Implement project and style APIs**

Implement the Project APIs and Style Source APIs exactly as defined in `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`.

- [ ] **Step 3: Implement Scene Plan APIs**

Implement the Scene Plan APIs exactly as defined in `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`.

- [ ] **Step 4: Implement conversation modification APIs**

Implement the Conversation APIs exactly as defined in `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`.

- [ ] **Step 5: Implement evidence lookup API**

Implement the Evidence APIs exactly as defined in `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`.

- [ ] **Step 6: Implement script, export, and run APIs**

Implement these API groups exactly as defined in `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`:

```text
Script APIs
Export APIs
Run And Progress APIs
```

- [ ] **Step 7: Run integration test**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest tests/integration/test_mvp_flow.py -q
```

Expected: full MVP flow passes with deterministic stub workers.

---

### Task 12: Frontend Workspace

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/frontend/package.json`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/tsconfig.json`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/vite.config.ts`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/vitest.setup.ts`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/Dockerfile`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/api/client.ts`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/app/App.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/ProjectSidebar.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/ConversationPane.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/StyleSourceSelector.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/AgentProgress.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/ResultPane.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/EvidenceModal.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/components/YamlPreview.tsx`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/tests/workspace.spec.tsx`

- [ ] **Step 1: Add frontend project config**

Create `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "test": "vitest run",
    "build": "vite build"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "typescript": "^5.5.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^15.0.0",
    "jsdom": "^24.1.0",
    "vitest": "^2.0.0"
  }
}
```

Create `frontend/vite.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
  },
});
```

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src", "vitest.setup.ts"]
}
```

Create `frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

Create `frontend/Dockerfile`:

```dockerfile
FROM node:20-slim

WORKDIR /app
COPY package.json /app/package.json
RUN npm install
COPY . /app
CMD ["npm", "run", "dev"]
```

- [ ] **Step 2: Write frontend tests**

```tsx
import { render, screen } from "@testing-library/react";
import App from "../app/App";

test("shows upload and style prompt before generation", () => {
  render(<App />);
  expect(screen.getByText("请上传小说并选择风格来源")).toBeInTheDocument();
});

test("yaml preview is read only", () => {
  render(<App initialYaml={"title: 雨夜归来"} />);
  expect(screen.getByText("title: 雨夜归来")).toBeInTheDocument();
  expect(screen.queryByRole("textbox", { name: /yaml/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Implement three-column layout**

Layout responsibilities:

```text
Left: new project button, project list, primary conversation, collapsible Scene Plan, generated script entry.
Middle: style source cards, conversation, upload attachment, collapsible Agent progress.
Right: Scene Plan or YAML read-only preview, evidence buttons, evidence modal, failure state.
```

All data loading must use typed functions from `frontend/src/api/client.ts` as defined in `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md`. Components must not call `fetch()` directly.

- [ ] **Step 4: Implement style source mutual exclusion**

UI behavior:

```text
Selecting built-in style disables custom text and history script upload.
Typing custom style disables history script upload.
Uploading history script disables custom text.
After Scene Plan confirmation, all style source controls become locked.
```

- [ ] **Step 5: Implement evidence modal API integration**

Behavior:

```text
Clicking a source evidence button calls GET /projects/{project_id}/evidence/by-content-block/{content_block_id}.
EvidenceModal shows chapter ID, paragraph ID, and source text.
EvidenceModal has a close button in the top right.
Evidence buttons are UI-layer controls and are not part of YAML content.
```

Implementation rule:

```text
EvidenceModal calls getEvidenceByContentBlock() from api/client.ts.
YamlPreview receives read-only YAML text and content block evidence markers from ResultPane state.
YamlPreview does not expose a textarea or editor control.
```

- [ ] **Step 6: Implement failure state**

User-visible text:

```text
本次生成未完成，请调整要求后重新发起
```

The frontend must show the failed stage and keep already generated content visible.

- [ ] **Step 7: Verify**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\frontend
npm test
```

Expected: workspace tests pass.

---

### Task 13: End-To-End Acceptance

**Files:**
- Create: `E:/七牛云/code/NovelScript-AI/backend/tests/e2e/test_acceptance_mvp.py`
- Create: `E:/七牛云/code/NovelScript-AI/frontend/src/tests/acceptance.spec.tsx`

- [ ] **Step 1: Backend acceptance assertions**

Assert these:

```text
Project creates primary conversation and active session.
Upload converts Markdown and creates chapter confirmation data.
Paragraph IDs are stable.
Style source is one of three mutually exclusive choices.
Scene Plan confirmation is explicit.
Style source locks after confirmation.
Internal script JSON contains content_block_id.
YAML preview is generated from clean output and is read-only.
traceability_index maps content_block_id to evidence.
Exported YAML and clean JSON omit internal trace fields.
run_id has run_step entries.
Budget consumption is recorded.
Upstream changes mark downstream artifacts stale.
```

- [ ] **Step 2: Run all backend tests**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\backend
pytest -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Run all frontend tests**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI\frontend
npm test
```

Expected: all frontend tests pass.

- [ ] **Step 4: Run Docker smoke test**

Run:

```powershell
cd E:\七牛云\code\NovelScript-AI
docker compose up --build
```

Expected:

```text
backend listens on http://localhost:8000
frontend listens on its configured local port
postgres is healthy
GET /health returns {"status":"ok"}
```

---

## Self-Review

Spec coverage:

- Input conversion, chapter confirmation, paragraph IDs: Tasks 4 and 11.
- PostgreSQL as authority and file storage boundary: Tasks 3, 10, 11.
- Three style sources, style reference upload, and mutual exclusion: Tasks 5, 11, and 12.
- Style lock after Scene Plan confirmation: Tasks 5, 8, 12.
- Long-context memory summarization without hard cropping: Task 7.
- Stage-specific prompt memory for Scene Plan, script generation, and conversation edits: Task 7.
- Multi-worker orchestration: Task 7.
- Validation Agent and programmatic validators: Tasks 2, 9, 13.
- `run_id`, `run_step_id`, budgets, developer logs: Task 6.
- Artifact invalidation and checkpoint behavior: Tasks 3 and 8.
- Internal JSON, read-only YAML preview, clean JSON export: Tasks 2 and 10.
- Frontend three-column UI and evidence modal: Task 12.
- Failure state without frontend manual review entry: Tasks 9 and 12.
- Frontend/backend API contract, DTOs, all listed endpoint responses, and typed client functions: `E:/七牛云/interface/NovelScript-AI/api-contract-v1.md` plus Tasks 11 and 12.

Known execution risks:

- LLM provider implementation must stay behind `worker_service.py` so tests can use deterministic stub workers.
- PDF extraction must remain text-only; scanned PDF OCR is outside MVP.
- DOC upload and DOC/PDF export require LibreOffice; Docker installs this runtime automatically.
- Developer logs can contain user text, so local retention and deletion rules must be implemented before enabling full Prompt logging.

Execution recommendation:

1. Implement backend through Task 11 first using deterministic stub workers.
2. Implement frontend Task 12 after backend API response shapes stabilize.
3. Run Task 13 acceptance only after both backend and frontend tests pass.
