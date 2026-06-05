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


class StubLLMProvider(LLMProvider):
    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text='{"status":"stub","task_type":"%s"}' % request.task_type,
            model_name="stub",
            usage=LLMUsage(input_tokens=len(request.prompt), output_tokens=32),
        )


class ConfiguredLLMProvider(LLMProvider):
    def generate(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("ConfiguredLLMProvider is a boundary stub until a vendor is selected")

