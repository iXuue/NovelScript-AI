from io import BytesIO

import pytest
from docx import Document

from app.services.document_conversion_service import UnsupportedDocumentTypeError
from app.services.input_adapter import normalize_to_markdown


def _docx_bytes(*paragraphs: str) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_doc_upload_is_converted_to_docx_before_markdown_extraction(monkeypatch):
    calls = []
    converted = _docx_bytes("Chapter 1", "The old door opens.")

    def fake_convert_document(content: bytes, source_suffix: str, target_suffix: str) -> bytes:
        calls.append((content, source_suffix, target_suffix))
        return converted

    monkeypatch.setattr("app.services.input_adapter.convert_document", fake_convert_document)

    markdown = normalize_to_markdown("novel.doc", b"legacy-doc-bytes")

    assert markdown == "Chapter 1\n\nThe old door opens."
    assert calls == [(b"legacy-doc-bytes", ".doc", ".docx")]


def test_unsupported_upload_extension_raises_typed_error():
    with pytest.raises(UnsupportedDocumentTypeError):
        normalize_to_markdown("novel.xlsx", b"not text")
