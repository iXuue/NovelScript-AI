from dataclasses import dataclass
import json
from typing import Any, Callable
from urllib import error, request

from app.core.config import Settings


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


class StubLLMProvider(LLMProvider):
    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text='{"status":"stub","task_type":"%s"}' % request.task_type,
            model_name="stub",
            usage=LLMUsage(input_tokens=len(request.prompt), output_tokens=32),
        )


ProviderTransport = Callable[[str, dict[str, str], dict[str, Any]], dict[str, Any]]


def _default_openai_transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI-compatible provider request failed: {exc.code} {response_body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"OpenAI-compatible provider request failed: {exc.reason}") from exc

    try:
        return json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("OpenAI-compatible provider returned invalid JSON") from exc


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        transport: ProviderTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.transport = transport or _default_openai_transport

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI-compatible provider")
        if not self.base_url:
            raise RuntimeError("OPENAI_BASE_URL is required for OpenAI-compatible provider")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL is required for OpenAI-compatible provider")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        response = self.transport(
            f"{self.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        return self._parse_response(response)

    def _parse_response(self, response: dict[str, Any]) -> LLMResponse:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("OpenAI-compatible provider response missing choices[0].message.content") from exc

        usage = response.get("usage") or {}
        return LLMResponse(
            text=content,
            model_name=self.model,
            usage=LLMUsage(
                input_tokens=int(usage.get("prompt_tokens") or 0),
                output_tokens=int(usage.get("completion_tokens") or 0),
            ),
        )


class ConfiguredLLMProvider(OpenAICompatibleLLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        super().__init__(base_url=base_url, api_key=api_key, model=model)


def provider_from_settings(settings: Settings) -> LLMProvider:
    return OpenAICompatibleLLMProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )

