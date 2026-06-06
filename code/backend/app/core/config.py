from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    app_name: str = "NovelScript AI"
    api_base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+psycopg://novelscript:novelscript@localhost:5433/novelscript"
    use_local_storage: bool = False
    local_data_root: str = "data"
    local_developer_logs_enabled: bool = True
    storage_root: str = "/app/storage"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    max_upload_characters: int = 2_000_000
    max_llm_prompt_chars: int = 24_000
    max_analysis_chunk_chars: int = 12_000
    max_evidence_items_per_prompt: int = 80
    max_quote_chars: int = 300


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def get_settings(env_file: str | Path | None = None) -> Settings:
    env_values = _read_env_file(Path(env_file) if env_file is not None else DEFAULT_ENV_FILE)
    return Settings(
        api_base_url=_env_value(env_values, "API_BASE_URL", default="http://localhost:8000"),
        database_url=_env_value(
            env_values,
            "DATABASE_URL",
            default="postgresql+psycopg://novelscript:novelscript@localhost:5433/novelscript",
        ),
        use_local_storage=_env_value(env_values, "USE_LOCAL_STORAGE", default="false").lower() == "true",
        local_data_root=_env_value(env_values, "LOCAL_DATA_ROOT", default="data"),
        local_developer_logs_enabled=_env_value(env_values, "LOCAL_DEVELOPER_LOGS_ENABLED", default="true").lower()
        == "true",
        storage_root=_env_value(env_values, "STORAGE_ROOT", default="/app/storage"),
        openai_base_url=_env_value(
            env_values,
            "OPENAI_BASE_URL",
            "openai_url",
            default="https://api.openai.com/v1",
        ),
        openai_api_key=_env_value(env_values, "OPENAI_API_KEY", "openai_key", default=""),
        openai_model=_env_value(env_values, "OPENAI_MODEL", "openai_model", default="gpt-4.1-mini"),
        max_upload_characters=int(_env_value(env_values, "MAX_UPLOAD_CHARACTERS", default="2000000")),
        max_llm_prompt_chars=int(_env_value(env_values, "MAX_LLM_PROMPT_CHARS", default="24000")),
        max_analysis_chunk_chars=int(_env_value(env_values, "MAX_ANALYSIS_CHUNK_CHARS", default="12000")),
        max_evidence_items_per_prompt=int(_env_value(env_values, "MAX_EVIDENCE_ITEMS_PER_PROMPT", default="80")),
        max_quote_chars=int(_env_value(env_values, "MAX_QUOTE_CHARS", default="300")),
    )


def _read_env_file(env_file: Path) -> dict[str, str]:
    if not env_file.exists():
        return {}
    return {key: value for key, value in dotenv_values(env_file).items() if value is not None}


def _env_value(env_values: dict[str, str], *keys: str, default: str) -> str:
    for key in keys:
        value = env_values.get(key)
        if value is not None:
            return value
    for key in keys:
        value = os.getenv(key)
        if value is not None:
            return value
    return default

