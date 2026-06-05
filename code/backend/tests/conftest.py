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
        elif request.task_type == "style_profile":
            text = (
                "采用悬疑短剧风格。对白短促克制，多用潜台词。"
                "场景短小精悍，切换频繁，通过硬切和悬念转场保持快节奏。"
                "冲突通过持续施压和信息差推进。旁白极少，动作描写服务于紧张氛围。"
            )
        elif request.task_type == "story_bible":
            text = (
                '{"title":"雨夜归来","story_type":"悬疑","tone":"冷峻紧张",'
                '"logline":"她在雨夜回到旧宅，旧信揭开隐藏的秘密。","theme":"归来与真相",'
                '"main_characters":[{"name":"她","role":"主角","goal":"寻找真相"}],'
                '"relationships":[],"locations":[{"name":"旧宅","description":"雨夜中的关键地点"}],'
                '"timeline":["雨夜归来"],"central_conflict":"主角归来后面对未知阻力",'
                '"foreshadowing":["旧信"]}'
            )
        elif request.task_type == "scene_plan":
            text = (
                '{"scenes":[{"scene_id":"S001","order":1,"title":"雨夜归来",'
                '"source_chapter_ids":["CH001"],"source_evidence_ids":["EV001"],'
                '"interior_exterior":"外景","location":"旧宅门口","time":"夜","characters":["她"],'
                '"must_cover_plot":["她在雨夜回到旧宅"],'
                '"must_keep_dialogue":["她回来了。"],'
                '"must_keep_visual_elements":["雨夜","旧宅门口"],'
                '"must_keep_foreshadowing":["旧信"],'
                '"scene_function":"建立人物回归","core_conflict":"她是否进入旧宅",'
                '"adaptation_note":"保留雨夜视觉元素"}]}'
            )
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
