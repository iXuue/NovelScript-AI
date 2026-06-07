from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path

from app.services.document_conversion_service import convert_document


@dataclass(frozen=True)
class UploadedFilePayload:
    filename: str
    content: bytes


def parse_multipart_file(body: bytes, content_type: str, field_name: str = "file") -> UploadedFilePayload:
    files = parse_multipart_files(body, content_type, field_names=[field_name])
    if not files:
        raise ValueError("file field is required")
    return files[0]


def parse_multipart_files(body: bytes, content_type: str, field_names: list[str] | None = None) -> list[UploadedFilePayload]:
    if "multipart/form-data" not in content_type:
        raise ValueError("multipart/form-data request is required")

    allowed_names = set(field_names or ["file", "files"])
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    files = []
    for part in message.iter_parts():
        params = dict(part.get_params(header="content-disposition", failobj=[]))
        if params.get("name") in allowed_names:
            filename = params.get("filename") or "upload.txt"
            files.append(UploadedFilePayload(filename=filename, content=part.get_payload(decode=True) or b""))
    if not files:
        raise ValueError("file field is required")
    return files


def normalize_to_markdown(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".doc":
        return _docx_to_markdown(convert_document(content, ".doc", ".docx"))
    if suffix in {".md", ".txt"}:
        return content.decode("utf-8-sig")
    if suffix == ".docx":
        return _docx_to_markdown(content)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise ValueError("pypdf is required to parse PDF files") from exc

        reader = PdfReader(BytesIO(content))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join(page for page in pages if page)
    from app.services.document_conversion_service import UnsupportedDocumentTypeError

    raise UnsupportedDocumentTypeError(f"unsupported file type: {suffix}")


def _docx_to_markdown(content: bytes) -> str:
    from docx import Document

    document = Document(BytesIO(content))
    return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())

