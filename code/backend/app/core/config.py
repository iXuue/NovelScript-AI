from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "NovelScript AI"
    api_base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+psycopg://novelscript:novelscript@postgres:5432/novelscript"
    local_developer_logs_enabled: bool = True
    storage_root: str = "/app/storage"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"


def get_settings() -> Settings:
    return Settings(
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://novelscript:novelscript@postgres:5432/novelscript",
        ),
        local_developer_logs_enabled=os.getenv("LOCAL_DEVELOPER_LOGS_ENABLED", "true").lower()
        == "true",
        storage_root=os.getenv("STORAGE_ROOT", "/app/storage"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
    )

