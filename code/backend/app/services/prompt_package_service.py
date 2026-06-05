from app.services.memory_service import build_prompt_memory


def build_prompt_package(stage: str, target: dict, latest_user_instruction: str | None = None, **memory_kwargs) -> dict:
    return {
        "stage": stage,
        "target": target,
        "latest_user_instruction": latest_user_instruction,
        "memory": build_prompt_memory(stage=stage, scope=target, **memory_kwargs).model_dump(),
        "forbidden_rules": [
            "do not expose developer logs",
            "do not edit scene plan after confirmation",
            "do not include trace fields in user exports",
        ],
    }

