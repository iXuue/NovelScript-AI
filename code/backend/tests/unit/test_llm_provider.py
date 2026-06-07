import json
import http.client
from urllib import request

from app.core.config import Settings
from app.services.llm_provider import (
    LLMRequest,
    OpenAICompatibleLLMProvider,
    StubLLMProvider,
    _default_openai_transport,
    provider_from_settings,
)


def test_stub_provider_returns_deterministic_json():
    provider = StubLLMProvider()
    response = provider.generate(LLMRequest(task_type="scene_plan", prompt="make scene plan"))
    assert response.model_name == "stub"
    assert response.text
    assert response.usage.input_tokens >= 0


def test_openai_compatible_provider_posts_chat_completion_request():
    captured = {}

    def transport(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }

    provider = OpenAICompatibleLLMProvider(
        base_url="https://llm.example.test/v1",
        api_key="secret-key",
        model="gpt-test",
        transport=transport,
    )

    response = provider.generate(
        LLMRequest(task_type="scene_plan", prompt="make scene plan", response_format="json")
    )

    assert captured["url"] == "https://llm.example.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert captured["payload"]["model"] == "gpt-test"
    assert captured["payload"]["messages"] == [{"role": "user", "content": "make scene plan"}]
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert json.loads(response.text) == {"ok": True}
    assert response.model_name == "gpt-test"
    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 7


def test_openai_compatible_provider_requires_api_key():
    provider = OpenAICompatibleLLMProvider(
        base_url="https://llm.example.test/v1",
        api_key="",
        model="gpt-test",
        transport=lambda url, headers, payload: {},
    )

    try:
        provider.generate(LLMRequest(task_type="scene_plan", prompt="make scene plan"))
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing API key to raise RuntimeError")


def test_openai_compatible_provider_wraps_incomplete_read():
    class IncompleteResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            raise http.client.IncompleteRead(b'{"choices": [')

    original_urlopen = request.urlopen
    request.urlopen = lambda http_request, timeout: IncompleteResponse()
    try:
        _default_openai_transport("https://llm.example.test/v1/chat/completions", {}, {"model": "gpt-test"})
    except RuntimeError as exc:
        assert "response read failed" in str(exc)
        assert "IncompleteRead" in str(exc)
    else:
        raise AssertionError("Expected incomplete read to raise RuntimeError")
    finally:
        request.urlopen = original_urlopen


def test_provider_from_settings_uses_openai_configuration():
    provider = provider_from_settings(
        Settings(
            openai_base_url="https://custom.example.test/v1",
            openai_api_key="custom-key",
            openai_model="custom-model",
        )
    )

    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.base_url == "https://custom.example.test/v1"
    assert provider.api_key == "custom-key"
    assert provider.model == "custom-model"

