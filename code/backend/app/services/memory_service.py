from app.domain.memory import PromptMemory


def build_prompt_memory(stage: str, scope: dict | None = None, **kwargs) -> PromptMemory:
    max_prompt_characters = kwargs.pop("max_prompt_characters", None)
    raw_context_characters = kwargs.pop("raw_context_characters", 0)
    compression_used = bool(max_prompt_characters and raw_context_characters > max_prompt_characters)

    layers = {key: value for key, value in kwargs.items() if value is not None}
    if compression_used:
        layers["compression_policy"] = "summary_artifacts_with_evidence_refs"

    return PromptMemory(
        stage=stage,
        scope=scope or {},
        layers=layers,
        compression_used=compression_used,
        raw_full_novel_included=False if compression_used else raw_context_characters <= (max_prompt_characters or raw_context_characters),
    )

