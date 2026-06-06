import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db, import_models
from app.main import app
from app.services.auth_service import create_user, issue_token
from app.services.llm_provider import LLMProvider, LLMRequest, LLMResponse, LLMUsage, get_llm_provider
from app.services.store import STORE


class FakeAnalysisLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self.fail_scene_plan_validation = False
        self.fail_script_scene_validation = False

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
            paragraph_id = paragraph_match.group(1) if paragraph_match else "CH001_P001"
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
                "冲突通过持续施压和信息差推进。"
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
        elif request.task_type == "scene_plan_validation":
            if self.fail_scene_plan_validation:
                text = (
                    '{"passed":false,"issues":[{"code":"missing_plot","message":"缺少关键剧情"}],'
                    '"suggestions":["补充旧信伏笔"],"coverage":{"chapter_ids":["CH001"],"evidence_ids":["EV001"]}}'
                )
            else:
                text = (
                    '{"passed":true,"issues":[],"suggestions":[],'
                    '"coverage":{"chapter_ids":["CH001"],"evidence_ids":["EV001"]}}'
                )
        elif request.task_type == "scene_plan_repair":
            text = (
                '{"scenes":[{"scene_id":"S001","order":1,"title":"雨夜归来",'
                '"source_chapter_ids":["CH001"],"source_evidence_ids":["EV001"],'
                '"interior_exterior":"外景","location":"旧宅门口","time":"夜","characters":["她"],'
                '"must_cover_plot":["她在雨夜回到旧宅"],'
                '"must_keep_dialogue":["她回来了。"],'
                '"must_keep_visual_elements":["雨夜","旧宅门口"],'
                '"must_keep_foreshadowing":["旧信"],'
                '"scene_function":"建立人物回归","core_conflict":"她是否进入旧宅",'
                '"adaptation_note":"补齐旧信伏笔并保留雨夜视觉元素"}]}'
            )
        elif request.task_type == "script_generation":
            text = (
                '{"scene_id":"S001","title":"雨夜归来","content_blocks":['
                '{"content_block_id":"CB001","type":"action","text":"她站在旧宅门口。",'
                '"speaker":null,"source_evidence_ids":["EV001"]},'
                '{"content_block_id":"CB002","type":"narration","text":"雨声压住她的呼吸。",'
                '"speaker":null,"source_evidence_ids":["EV001"]}'
                ']}'
            )
        elif request.task_type == "script_scene_validation":
            if self.fail_script_scene_validation:
                text = (
                    '{"passed":false,"issues":[{"code":"missing_dialogue","message":"必保对白未落实"}],'
                    '"suggestions":["补写她回来了这句对白"],'
                    '"coverage":{"must_cover_plot":["她在雨夜回到旧宅"],"must_keep_dialogue":[],'
                    '"must_keep_visual_elements":["雨夜","旧宅门口"],"must_keep_foreshadowing":["旧信"]}}'
                )
            else:
                text = (
                    '{"passed":true,"issues":[],"suggestions":[],'
                    '"coverage":{"must_cover_plot":["她在雨夜回到旧宅"],"must_keep_dialogue":["她回来了。"],'
                    '"must_keep_visual_elements":["雨夜","旧宅门口"],"must_keep_foreshadowing":["旧信"]}}'
                )
        elif request.task_type == "script_scene_repair":
            text = (
                '{"scene_id":"S001","title":"雨夜归来","scene_info":"外景 / 旧宅门口 / 夜",'
                '"characters":["她"],"scene_purpose":"建立人物回归","core_conflict":"她是否进入旧宅",'
                '"content_blocks":['
                '{"content_block_id":"CB001","type":"action","text":"她站在旧宅门口，雨水顺着门檐落下。",'
                '"speaker":null,"source_evidence_ids":["EV001"]},'
                '{"content_block_id":"CB002","type":"dialogue","text":"她回来了。",'
                '"speaker":"她","source_evidence_ids":["EV001"]}'
                ']}'
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
    with Session(engine) as session:
        user = create_user(session, "test-user", "password123")
        user_id = user.user_id
        token = issue_token(session, user)

    def override_get_llm_provider():
        return fake_provider

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_provider] = override_get_llm_provider
    try:
        test_client = TestClient(app)
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        test_client.auth_token = token
        test_client.auth_user_id = user_id
        test_client.fake_llm_provider = fake_provider
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def unauth_client():
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
