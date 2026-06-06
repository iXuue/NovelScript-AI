from collections.abc import Callable, Iterable
from typing import TypeVar

from app.services.llm_provider import LLMProvider, LLMRequest, LLMResponse


DEFAULT_MAX_LLM_PROMPT_CHARS = 24_000
DEFAULT_MAX_ANALYSIS_CHUNK_CHARS = 12_000
DEFAULT_MAX_EVIDENCE_ITEMS_PER_PROMPT = 80
DEFAULT_MAX_QUOTE_CHARS = 300
DEFAULT_MAX_STYLE_SOURCE_CHARS = 12_000

T = TypeVar("T")


def estimate_prompt_size(prompt: str) -> int:
    return len(prompt)


def estimate_tokens(prompt: str) -> int:
    return max(1, len(prompt))


def truncate_text(text: str, max_chars: int, marker: str = "\n[TRUNCATED]") -> str:
    if len(text) <= max_chars:
        return text
    keep = max(0, max_chars - len(marker))
    return f"{text[:keep]}{marker}"


def chunk_items_by_text(items: list[T], text_getter: Callable[[T], str], max_chars: int) -> list[list[T]]:
    chunks: list[list[T]] = []
    current: list[T] = []
    current_chars = 0
    for item in items:
        text_chars = len(text_getter(item))
        if current and current_chars + text_chars > max_chars:
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += text_chars
    if current:
        chunks.append(current)
    return chunks


def compact_lines(lines: Iterable[str], max_chars: int) -> str:
    selected: list[str] = []
    used = 0
    omitted = 0
    for line in lines:
        line_len = len(line) + 1
        if selected and used + line_len > max_chars:
            omitted += 1
            continue
        if not selected and line_len > max_chars:
            selected.append(truncate_text(line, max_chars))
            used = max_chars
            continue
        selected.append(line)
        used += line_len
    if omitted:
        selected.append(f"[OMITTED {omitted} ITEMS DUE TO CONTEXT BUDGET]")
    return "\n".join(selected)


def clamp_prompt(prompt: str, max_chars: int = DEFAULT_MAX_LLM_PROMPT_CHARS) -> str:
    return truncate_text(prompt, max_chars)


def rank_evidence_items(evidence_items: list[T], limit: int = DEFAULT_MAX_EVIDENCE_ITEMS_PER_PROMPT) -> list[T]:
    return sorted(
        evidence_items,
        key=lambda item: (
            not bool(getattr(item, "must_keep", False)),
            -int(getattr(item, "importance", 0) or 0),
            str(getattr(item, "evidence_id", "")),
        ),
    )[:limit]


def generate_with_context_log(
    llm_provider: LLMProvider,
    *,
    task_type: str,
    prompt: str,
    response_format: str = "json",
    db=None,
    project_id: str | None = None,
    step_type: str | None = None,
    chunk_range: dict | None = None,
    source_item_count: int | None = None,
    included_item_count: int | None = None,
    max_chars: int = DEFAULT_MAX_LLM_PROMPT_CHARS,
) -> LLMResponse:
    clamped_prompt = clamp_prompt(prompt, max_chars)
    response = llm_provider.generate(
        LLMRequest(
            task_type=task_type,
            prompt=clamped_prompt,
            response_format=response_format,
        )
    )
    _write_llm_context_log(
        db,
        {
            "event_type": "llm_request",
            "project_id": project_id,
            "step_type": step_type or task_type,
            "task_type": task_type,
            "response_format": response_format,
            "model_name": response.model_name,
            "raw_prompt_characters": len(prompt),
            "prompt_characters": len(clamped_prompt),
            "truncated_characters": max(0, len(prompt) - len(clamped_prompt)),
            "estimated_input_tokens": estimate_tokens(clamped_prompt),
            "provider_input_tokens": response.usage.input_tokens,
            "provider_output_tokens": response.usage.output_tokens,
            "token_estimate_used": response.usage.input_tokens <= 0,
            "chunk_range": chunk_range,
            "source_item_count": source_item_count,
            "included_item_count": included_item_count,
            "omitted_item_count": _omitted_count(source_item_count, included_item_count),
        },
    )
    return response


def _omitted_count(source_item_count: int | None, included_item_count: int | None) -> int | None:
    if source_item_count is None or included_item_count is None:
        return None
    return max(0, source_item_count - included_item_count)


def _write_llm_context_log(db, payload: dict) -> None:
    if db is None:
        return
    from app.services.developer_log_service import write_developer_log

    write_developer_log(None, payload, db)
