from app.core.config import get_settings


def test_get_settings_reads_openai_values_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "openai_url=https://llm.example.test\n"
        "openai_key=test-key\n"
        "openai_model=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("openai_url", raising=False)
    monkeypatch.delenv("openai_key", raising=False)
    monkeypatch.delenv("openai_model", raising=False)

    settings = get_settings(env_file=env_file)

    assert settings.openai_base_url == "https://llm.example.test"
    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "test-model"


def test_uppercase_openai_environment_values_override_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "openai_url=https://from-file.example.test\n"
        "openai_key=file-key\n"
        "openai_model=file-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_BASE_URL", "https://from-env.example.test")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_MODEL", "env-model")

    settings = get_settings(env_file=env_file)

    assert settings.openai_base_url == "https://from-env.example.test"
    assert settings.openai_api_key == "env-key"
    assert settings.openai_model == "env-model"
