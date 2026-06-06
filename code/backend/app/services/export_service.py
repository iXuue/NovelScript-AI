from copy import deepcopy
from io import BytesIO
import json

import yaml


INTERNAL_KEYS = {"content_block_id", "source_evidence_ids", "source_paragraph_ids", "paragraph_id", "traceability_index"}
EXPORT_EXTENSIONS = {
    "yaml": "yaml",
    "markdown": "md",
    "docx": "docx",
    "pdf": "pdf",
    "txt": "txt",
    "clean_json": "json",
}
EXPORT_CONTENT_TYPES = {
    "yaml": "application/x-yaml; charset=utf-8",
    "markdown": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "clean_json": "application/json; charset=utf-8",
}


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


def serialize_export(internal: dict, export_format: str) -> str | bytes:
    clean = to_user_clean_json(internal)
    if export_format == "yaml":
        return to_yaml_preview(clean)
    if export_format == "clean_json":
        return json.dumps(clean, ensure_ascii=False, indent=2)
    if export_format in {"markdown", "txt"}:
        return to_yaml_preview(clean)
    if export_format == "docx":
        return _serialize_docx(clean)
    if export_format == "pdf":
        raise ValueError("pdf_not_available")
    raise ValueError(f"unsupported export format: {export_format}")


def _serialize_docx(clean: dict) -> bytes:
    from docx import Document

    document = Document()
    document.add_heading(str(clean.get("title") or "Script"), level=1)
    for scene in clean.get("scenes") or []:
        document.add_heading(str(scene.get("title") or scene.get("scene_id") or "Scene"), level=2)
        scene_info = scene.get("scene_info")
        if scene_info:
            document.add_paragraph(str(scene_info))
        for block in scene.get("content_blocks") or []:
            speaker = block.get("speaker")
            text = block.get("text")
            if speaker:
                document.add_paragraph(str(speaker))
            if text:
                document.add_paragraph(str(text))
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
