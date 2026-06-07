from app.services.export_service import serialize_export


def test_doc_export_converts_generated_docx(monkeypatch):
    calls = []

    def fake_convert_document(content: bytes, source_suffix: str, target_suffix: str) -> bytes:
        calls.append((content, source_suffix, target_suffix))
        return b"DOC_BYTES"

    monkeypatch.setattr("app.services.export_service.convert_document", fake_convert_document)

    exported = serialize_export({"title": "Script", "scenes": []}, "doc")

    assert exported == b"DOC_BYTES"
    assert calls[0][0].startswith(b"PK")
    assert calls[0][1:] == (".docx", ".doc")


def test_pdf_export_converts_generated_docx(monkeypatch):
    calls = []

    def fake_convert_document(content: bytes, source_suffix: str, target_suffix: str) -> bytes:
        calls.append((content, source_suffix, target_suffix))
        return b"%PDF-FAKE"

    monkeypatch.setattr("app.services.export_service.convert_document", fake_convert_document)

    exported = serialize_export({"title": "Script", "scenes": []}, "pdf")

    assert exported == b"%PDF-FAKE"
    assert calls[0][0].startswith(b"PK")
    assert calls[0][1:] == (".docx", ".pdf")
