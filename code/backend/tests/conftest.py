import pytest
import re
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, import_models
from app.core.database import get_db
from app.main import app
from app.services.llm_provider import LLMProvider, LLMRequest, LLMResponse, LLMUsage, get_llm_provider
from app.services.store import STORE


class FakeAnalysisLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if request.task_type == "chapter_summary":
            text = (
                '{"summary":"LLM章节摘要","key_events":["她回来了"],"characters":["她"],'
                '"locations":["旧宅"],"conflicts":["归来后的未知阻力"],"foreshadowing":["旧信"],'
                '"adaptation_suggestions":["保留雨夜归来的戏剧性"]}'
            )
        elif request.task_type == "evidence_extraction":
            paragraph_match = re.search(r"- (CH\d+_P\d+): (.+)", request.prompt)
            paragraph_id_match = paragraph_match
            paragraph_id = paragraph_id_match.group(1) if paragraph_id_match else "CH001_P001"
            quote = paragraph_match.group(2) if paragraph_match else "她回来了。"
            text = (
                '{"evidence":[{"paragraph_id":"%s","quote":"%s",'
                '"evidence_type":"关键事件","explanation":"主角归来推动剧情。",'
                '"related_characters":["她"],"related_locations":[],"related_plot_points":["归来"],'
                '"importance":5,"must_keep":true}]}'
            ) % (paragraph_id, quote)
        else:
            text = "{}"
        return LLMResponse(text=text, model_name="fake-analysis", usage=LLMUsage(input_tokens=1, output_tokens=1))


@pytest.fixture(autouse=True)
def reset_store():
    STORE.reset()
    yield
    STORE.reset()


@pytest.fixture()
def client():
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
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def test_db():
    import_models()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

