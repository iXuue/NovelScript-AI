from app.services.llm_provider import LLMRequest, StubLLMProvider


def test_stub_provider_returns_deterministic_json():
    provider = StubLLMProvider()
    response = provider.generate(LLMRequest(task_type="scene_plan", prompt="make scene plan"))
    assert response.model_name == "stub"
    assert response.text
    assert response.usage.input_tokens >= 0

