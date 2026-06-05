from copy import deepcopy
import json

import yaml


INTERNAL_KEYS = {"content_block_id", "source_evidence_ids", "paragraph_id", "traceability_index"}


def _remove_internal(value):
    if isinstance(value, dict):
        return {k: _remove_internal(v) for k, v in value.items() if k not in INTERNAL_KEYS}
    if isinstance(value, list):
        return [_remove_internal(item) for item in value]
    return value


def to_user_clean_json(internal: dict) -> dict:
    return _remove_internal(deepcopy(internal))


def to_yaml_preview(internal_or_clean: dict) -> str:
    clean = to_user_clean_json(internal_or_clean)
    return yaml.safe_dump(clean, allow_unicode=True, sort_keys=False)


def serialize_export(internal: dict, export_format: str) -> str:
    clean = to_user_clean_json(internal)
    if export_format == "clean_json":
        return json.dumps(clean, ensure_ascii=False, indent=2)
    if export_format == "yaml":
        return to_yaml_preview(clean)
    if export_format in {"markdown", "txt"}:
        return to_yaml_preview(clean)
    if export_format in {"docx", "pdf"}:
        return to_yaml_preview(clean)
    raise ValueError(f"unsupported export format: {export_format}")

