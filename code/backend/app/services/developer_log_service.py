SENSITIVE_KEYS = {"api_key", "database_url", "password", "secret", "token"}


def redact_sensitive(payload: dict) -> dict:
    return {key: ("<redacted>" if key.lower() in SENSITIVE_KEYS else value) for key, value in payload.items()}


def write_developer_log(run_id: str, payload: dict) -> None:
    return None

