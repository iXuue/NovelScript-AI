from dataclasses import dataclass
import threading
import time

import pytest

from app.services.analysis_worker_service import (
    _chapter_summary_prompt,
    _evidence_prompt,
    _generate_evidence_payloads,
    _generate_summary_payload,
    run_analysis_payload_generation,
)
from app.services.context_budget_service import DEFAULT_MAX_LLM_PROMPT_CHARS
from app.services.llm_provider import LLMProvider, LLMRequest, LLMResponse, LLMUsage


@dataclass
class FakeChapter:
    chapter_id: str = "CH001"
    title: str = "第一章 雨夜"
    raw_text: str = "她回来了。"


@dataclass
class FakeParagraph:
    paragraph_id: str
    text: str


class StaticProvider(LLMProvider):
    def __init__(self, text: str) -> None:
        self.text = text

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text=self.text, model_name="test-model", usage=LLMUsage(input_tokens=1, output_tokens=1))


class BlockingProvider(LLMProvider):
    def __init__(self, expected_calls: int) -> None:
        self.barrier = threading.Barrier(expected_calls)
        self.lock = threading.Lock()
        self.events: list[tuple[str, str, float]] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        with self.lock:
            self.events.append((request.task_type, "start", time.perf_counter()))
        self.barrier.wait(timeout=5)
        time.sleep(0.05)
        with self.lock:
            self.events.append((request.task_type, "end", time.perf_counter()))
        if request.task_type == "chapter_summary":
            text = (
                '{"summary":"并发摘要","key_events":[],"characters":[],"locations":[],'
                '"conflicts":[],"foreshadowing":[],"adaptation_suggestions":[]}'
            )
        else:
            paragraph_id = "CH002_P001" if "- CH002_P001:" in request.prompt else "CH001_P001"
            quote = "第一章内容" if paragraph_id == "CH001_P001" else "第二章内容"
            text = (
                '{"evidence":[{"paragraph_id":"%s","quote":"%s","evidence_type":"关键事件",'
                '"explanation":"说明","related_characters":[],"related_locations":[],'
                '"related_plot_points":[],"importance":3,"must_keep":true}]}'
            ) % (paragraph_id, quote)
        return LLMResponse(text=text, model_name="blocking", usage=LLMUsage(input_tokens=1, output_tokens=1))


class ChunkTrackingProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        paragraph_id = "CH001_P001"
        quote = "长段落内容"
        for line in request.prompt.splitlines():
            if line.startswith("- CH"):
                paragraph_id, quote = line.removeprefix("- ").split(": ", 1)
                break
        if request.task_type == "chapter_summary":
            text = (
                '{"summary":"分块摘要","key_events":["分块事件"],"characters":[],"locations":[],'
                '"conflicts":[],"foreshadowing":[],"adaptation_suggestions":[]}'
            )
        else:
            text = (
                '{"evidence":[{"paragraph_id":"%s","quote":"%s","evidence_type":"关键事件",'
                '"explanation":"说明","related_characters":[],"related_locations":[],"related_plot_points":[],'
                '"importance":3,"must_keep":true}]}'
            ) % (paragraph_id, quote[:120])
        return LLMResponse(text=text, model_name="chunk-tracker", usage=LLMUsage(input_tokens=1, output_tokens=1))


def test_chapter_summary_prompt_contains_schema_and_guardrails():
    prompt = _chapter_summary_prompt(FakeChapter(), [FakeParagraph("CH001_P001", "她回来了。")])

    assert "只基于给定段落" in prompt
    assert "不要编造" in prompt
    assert "遗漏风险" in prompt
    assert '"summary"' in prompt
    assert "CH001_P001" in prompt


def test_evidence_prompt_contains_allowed_types_and_quote_rules():
    prompt = _evidence_prompt(FakeChapter(), [FakeParagraph("CH001_P001", "她回来了。")])

    assert "证据类型只能使用" in prompt
    assert "关键事件" in prompt
    assert "quote 必须是原文摘录" in prompt
    assert "不得引用不存在的 paragraph_ids" in prompt
    assert '"must_keep"' in prompt


def test_summary_response_requires_non_empty_summary():
    provider = StaticProvider(
        '{"summary":"","key_events":[],"characters":[],"locations":[],"conflicts":[],'
        '"foreshadowing":[],"adaptation_suggestions":[],"omission_risks":[]}'
    )

    with pytest.raises(RuntimeError, match="summary"):
        _generate_summary_payload(FakeChapter(), [FakeParagraph("CH001_P001", "她回来了。")], provider)


def test_evidence_response_rejects_unsupported_evidence_type():
    provider = StaticProvider(
        '{"evidence":[{"paragraph_id":"CH001_P001","quote":"她回来了。",'
        '"evidence_type":"不存在类型","explanation":"说明","related_characters":[],'
        '"related_locations":[],"related_plot_points":[],"importance":3,"must_keep":true}]}'
    )

    with pytest.raises(RuntimeError, match="evidence_type"):
        _generate_evidence_payloads(FakeChapter(), [FakeParagraph("CH001_P001", "她回来了。")], provider)


def test_evidence_response_rejects_quote_not_found_in_source_paragraph():
    provider = StaticProvider(
        '{"evidence":[{"paragraph_id":"CH001_P001","quote":"不是原文",'
        '"evidence_type":"关键事件","explanation":"说明","related_characters":[],'
        '"related_locations":[],"related_plot_points":[],"importance":3,"must_keep":true}]}'
    )

    with pytest.raises(RuntimeError, match="quote"):
        _generate_evidence_payloads(FakeChapter(), [FakeParagraph("CH001_P001", "她回来了。")], provider)


def test_evidence_response_accepts_multiple_paragraph_ids_for_one_evidence():
    provider = StaticProvider(
        '{"evidence":[{"paragraph_ids":["CH001_P001","CH001_P002"],"quote":"alpha\\nbeta",'
        '"evidence_type":"\\u5173\\u952e\\u4e8b\\u4ef6","explanation":"note","related_characters":[],'
        '"related_locations":[],"related_plot_points":[],"importance":3,"must_keep":true}]}'
    )

    payloads = _generate_evidence_payloads(
        FakeChapter(),
        [FakeParagraph("CH001_P001", "alpha"), FakeParagraph("CH001_P002", "beta")],
        provider,
    )

    assert payloads[0]["paragraph_ids"] == ["CH001_P001", "CH001_P002"]


def test_analysis_payload_generation_runs_summary_and_evidence_for_each_chapter_concurrently():
    provider = BlockingProvider(expected_calls=4)
    chapters = [
        (FakeChapter(chapter_id="CH001", title="第一章", raw_text="第一章内容"), [FakeParagraph("CH001_P001", "第一章内容")]),
        (FakeChapter(chapter_id="CH002", title="第二章", raw_text="第二章内容"), [FakeParagraph("CH002_P001", "第二章内容")]),
    ]

    started_at = time.perf_counter()
    result = run_analysis_payload_generation(chapters, provider)
    elapsed = time.perf_counter() - started_at

    task_starts = [event for event in provider.events if event[1] == "start"]
    assert len(task_starts) == 4
    assert {event[0] for event in task_starts} == {"chapter_summary", "evidence_extraction"}
    assert elapsed < 0.2
    assert len(result["summaries"]) == 2
    assert len(result["evidence_payloads_by_chapter"]) == 2


def test_long_chapter_analysis_splits_prompts_under_context_budget():
    paragraphs = [
        FakeParagraph(f"CH001_P{i:03d}", f"长段落内容 {i} " + ("雨夜线索" * 80))
        for i in range(1, 501)
    ]
    provider = ChunkTrackingProvider()

    summary = _generate_summary_payload(FakeChapter(), paragraphs, provider)
    evidence = _generate_evidence_payloads(FakeChapter(), paragraphs, provider)

    assert summary["summary"]
    assert evidence
    assert len(provider.requests) > 2
    assert max(len(request.prompt) for request in provider.requests) <= DEFAULT_MAX_LLM_PROMPT_CHARS
