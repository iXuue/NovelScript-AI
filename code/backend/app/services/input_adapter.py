from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path


@dataclass(frozen=True)
class UploadedFilePayload:
    filename: str
    content: bytes


def parse_multipart_file(body: bytes, content_type: str, field_name: str = "file") -> UploadedFilePayload:
    if "multipart/form-data" not in content_type:
        raise ValueError("multipart/form-data request is required")

    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    for part in message.iter_parts():
        params = dict(part.get_params(header="content-disposition", failobj=[]))
        if params.get("name") == field_name:
            filename = params.get("filename") or "upload.txt"
            return UploadedFilePayload(filename=filename, content=part.get_payload(decode=True) or b"")
    raise ValueError("file field is required")


def normalize_to_markdown(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".doc":
        raise ValueError(".doc is not supported in MVP")
    if suffix in {".md", ".txt"}:
        return content.decode("utf-8-sig")
    if suffix == ".docx":
        from docx import Document

        document = Document(BytesIO(content))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise ValueError("pypdf is required to parse PDF files") from exc

        reader = PdfReader(BytesIO(content))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join(page for page in pages if page)
    raise ValueError(f"unsupported file type: {suffix}")

