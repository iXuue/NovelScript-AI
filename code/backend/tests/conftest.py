from contextlib import contextmanager
import json
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, import_models
from app.main import app
from app.services.llm_provider import LLMProvider, LLMRequest, LLMResponse, LLMUsage, get_llm_provider
from app.services.store import STORE


def json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


class FakeAnalysisLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self.fail_scene_plan_validation = False
        self.fail_script_scene_validation = False
        self.fail_next_request = False

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if self.fail_next_request:
            self.fail_next_request = False
            raise RuntimeError("fake LLM failure")
        if request.task_type == "chapter_summary":
            text = json_dumps(
                {
                    "summary": "Chapter summary",
                    "narrative_function": "Establish the protagonist's return and set up the central mystery.",
                    "key_events": ["She returns"],
                    "characters": ["She"],
                    "locations": ["Old house"],
                    "conflicts": ["Unknown resistance after returning"],
                    "emotional_beats": ["tension", "nostalgia"],
                    "foreshadowing": ["Old letter"],
                    "dialogue_candidates": ["I am back."],
                    "visual_elements": ["Rainy night", "Old house gate"],
                    "adaptation_suggestions": ["Keep the rainy return as the main visual beat"],
                }
            )
        elif request.task_type == "evidence_extraction":
            paragraph_match = re.search(r"- (CH\d+_P\d+): (.+)", request.prompt)
            paragraph_id = paragraph_match.group(1) if paragraph_match else "CH001_P001"
            quote = paragraph_match.group(2) if paragraph_match else "She returns."
            text = json_dumps(
                {
                    "evidence": [
                        {
                            "paragraph_id": paragraph_id,
                            "quote": quote,
                            "evidence_type": "key_event",
                            "explanation": "The return drives the plot.",
                            "related_characters": ["She"],
                            "related_locations": [],
                            "related_plot_points": ["Return"],
                            "importance": 5,
                            "must_keep": True,
                        }
                    ]
                }
            )
        elif request.task_type == "style_profile":
            text = "Suspense style. Use concise action, controlled dialogue, and fast scene transitions."
        elif request.task_type == "story_bible":
            text = json_dumps(
                {
                    "title": "Rainy Return",
                    "story_type": "suspense",
                    "tone": "cold and tense",
                    "logline": "She returns to the old house and uncovers a hidden secret.",
                    "theme": "return and truth",
                    "main_characters": [{"name": "She", "role": "protagonist", "goal": "find the truth"}],
                    "relationships": [],
                    "locations": [{"name": "Old house", "description": "A key location in the rain"}],
                    "timeline": ["Rainy return"],
                    "central_conflict": "The protagonist faces unknown resistance after returning.",
                    "foreshadowing": ["Old letter"],
                }
            )
        elif request.task_type in {"scene_plan", "scene_plan_chapter", "scene_plan_repair"}:
            paragraph_match = re.search(r'"paragraph_id":\s*"(CH\d+_P\d+)"', request.prompt)
            source_paragraph_id = paragraph_match.group(1) if paragraph_match else "CH001_P001"
            chapter_match = re.search(r'"chapter_id":\s*"(CH\d+)"', request.prompt)
            source_chapter_id = chapter_match.group(1) if chapter_match else source_paragraph_id.split("_", 1)[0]
            feedback_prefix = "Feedback " if "confirmed_feedback_plan:" in request.prompt else ""
            text = json_dumps(
                {
                    "scenes": [
                        {
                            "scene_id": "S001",
                            "order": 1,
                            "title": f"{feedback_prefix}Rainy Return",
                            "source_chapter_ids": [source_chapter_id],
                            "source_evidence_ids": [],
                            "source_paragraph_ids": [source_paragraph_id],
                            "interior_exterior": "EXT",
                            "location": "Old house gate",
                            "time": "Night",
                            "characters": ["She"],
                            "must_cover_plot": ["She returns to the old house in the rain"],
                            "must_keep_dialogue": ["I am back."],
                            "must_keep_visual_elements": ["Rainy night", "Old house gate"],
                            "must_keep_foreshadowing": ["Old letter"],
                            "scene_function": "Establish the protagonist's return",
                            "core_conflict": "Whether she enters the old house",
                            "adaptation_note": "Keep the rain as a visual pressure point.",
                        }
                    ]
                }
            )
        elif request.task_type == "scene_plan_validation":
            text = json_dumps(
                {
                    "passed": not self.fail_scene_plan_validation,
                    "issues": [] if not self.fail_scene_plan_validation else [{"code": "missing_plot", "message": "Missing plot"}],
                    "suggestions": [],
                    "coverage": {"chapter_ids": ["CH001"], "paragraph_ids": ["CH001_P001"]},
                }
            )
        elif request.task_type == "feedback_plan":
            target_payload = {}
            target_match = re.search(r"target:\n({.*?})\n\ncontext_without_full_source_text:", request.prompt, re.S)
            if target_match:
                target_payload = json.loads(target_match.group(1))
            target_type = target_payload.get("type") or "script"
            intent_by_target = {
                "scene_plan": "regenerate_scene_plan",
                "script": "regenerate_script",
                "chapters": "modify_chapter",
            }
            chapter_ids = target_payload.get("chapter_ids") if isinstance(target_payload.get("chapter_ids"), list) else []
            text = json_dumps(
                {
                    "intent": intent_by_target[target_type],
                    "affected_scope": {
                        "chapter_ids": chapter_ids,
                        "scene_ids": [],
                    },
                    "modification_plan": ["Apply the user's feedback while preserving source facts."],
                    "needs_source_text": True,
                    "source_requests": [
                        {
                            "paragraph_ids": ["CH001_P001"],
                            "scene_ids": [],
                            "chapter_ids": chapter_ids,
                            "reason": "Use the source paragraph to keep factual continuity.",
                        }
                    ],
                    "user_confirmation_required": True,
                }
            )
        elif request.task_type == "script_generation":
            scene_matches = re.findall(r'"scene_id":\s*"(S\d+)"', request.prompt)
            scene_id = scene_matches[-1] if scene_matches else "S001"
            paragraph_matches = re.findall(r'"source_paragraph_ids":\s*\[\s*"(CH\d+_P\d+)"', request.prompt)
            source_paragraph_id = paragraph_matches[-1] if paragraph_matches else "CH001_P001"
            action_text = (
                "Feedback revised scene from the confirmed plan."
                if "confirmed_feedback_plan:" in request.prompt
                else "She stands outside the old house gate."
            )
            text = json_dumps(
                {
                    "scene_id": scene_id,
                    "title": "Rainy Return",
                    "scene_info": "EXT / Old house gate / Night",
                    "characters": ["She"],
                    "scene_purpose": "Establish the protagonist's return",
                    "core_conflict": "Whether she enters the old house",
                    "content_blocks": [
                        {
                            "content_block_id": "CB001",
                            "type": "action",
                            "text": action_text,
                            "speaker": None,
                            "parenthetical": None,
                            "source_evidence_ids": [],
                            "source_paragraph_ids": [source_paragraph_id],
                        },
                        {
                            "content_block_id": "CB002",
                            "type": "narration",
                            "text": "Rain presses down on her breath.",
                            "speaker": None,
                            "parenthetical": None,
                            "source_evidence_ids": [],
                            "source_paragraph_ids": [source_paragraph_id],
                        },
                    ],
                }
            )
        elif request.task_type == "script_scene_validation":
            text = json_dumps(
                {
                    "passed": not self.fail_script_scene_validation,
                    "issues": []
                    if not self.fail_script_scene_validation
                    else [{"code": "missing_dialogue", "message": "Required dialogue is missing"}],
                    "suggestions": [],
                    "coverage": {"source_paragraph_ids": ["CH001_P001"]},
                }
            )
        elif request.task_type == "script_scene_repair":
            scene_matches = re.findall(r'"scene_id":\s*"(S\d+)"', request.prompt)
            scene_id = scene_matches[-1] if scene_matches else "S001"
            paragraph_matches = re.findall(r'"source_paragraph_ids":\s*\[\s*"(CH\d+_P\d+)"', request.prompt)
            source_paragraph_id = paragraph_matches[-1] if paragraph_matches else "CH001_P001"
            text = json_dumps(
                {
                    "scene_id": scene_id,
                    "title": "Rainy Return",
                    "scene_info": "EXT / Old house gate / Night",
                    "characters": ["She"],
                    "scene_purpose": "Establish the protagonist's return",
                    "core_conflict": "Whether she enters the old house",
                    "content_blocks": [
                        {
                            "content_block_id": "CB001",
                            "type": "action",
                            "text": "She stands outside the old house gate as rain drops from the eaves.",
                            "speaker": None,
                            "parenthetical": None,
                            "source_evidence_ids": [],
                            "source_paragraph_ids": [source_paragraph_id],
                        },
                        {
                            "content_block_id": "CB002",
                            "type": "dialogue",
                            "text": "I am back.",
                            "speaker": "She",
                            "parenthetical": "(低声)",
                            "source_evidence_ids": [],
                            "source_paragraph_ids": [source_paragraph_id],
                        },
                    ],
                }
            )
        else:
            text = "{}"
        return LLMResponse(text=text, model_name="fake-analysis", usage=LLMUsage(input_tokens=1, output_tokens=1))


@pytest.fixture(autouse=True)
def reset_store():
    STORE.reset()
    yield
    STORE.reset()


@contextmanager
def _test_client_context(authenticated: bool):
    import_models()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    fake_provider = FakeAnalysisLLMProvider()

    def override_get_llm_provider():
        return fake_provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_provider] = override_get_llm_provider
    try:
        test_client = TestClient(app)
        test_client.fake_llm_provider = fake_provider
        if authenticated:
            response = test_client.post(
                "/auth/register",
                json={"login_id": "testuser", "password": "password123"},
            )
            assert response.status_code == 200, response.text
            session = response.json()
            test_client.headers.update({"Authorization": f"Bearer {session['token']}"})
            test_client.auth_user = session["user"]
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client():
    with _test_client_context(authenticated=True) as test_client:
        yield test_client


@pytest.fixture()
def unauth_client():
    with _test_client_context(authenticated=False) as test_client:
        yield test_client


@pytest.fixture()
def test_db():
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
