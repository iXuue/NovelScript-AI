from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from app.core.config import get_settings


class UnsupportedDocumentTypeError(ValueError):
    pass


class DocumentConverterUnavailableError(RuntimeError):
    pass


class DocumentConversionError(RuntimeError):
    pass


CONVERT_TO = {
    (".doc", ".docx"): "docx",
    (".docx", ".doc"): "doc:MS Word 97",
    (".docx", ".pdf"): "pdf:writer_pdf_Export",
}


def convert_document(content: bytes, source_suffix: str, target_suffix: str) -> bytes:
    source_suffix = _normalize_suffix(source_suffix)
    target_suffix = _normalize_suffix(target_suffix)
    convert_to = CONVERT_TO.get((source_suffix, target_suffix))
    if convert_to is None:
        raise UnsupportedDocumentTypeError(f"unsupported document conversion: {source_suffix} to {target_suffix}")

    settings = get_settings()
    soffice = _resolve_soffice_binary(settings.soffice_binary)
    with TemporaryDirectory(prefix="novelscript-doc-convert-") as temp_dir:
        workspace = Path(temp_dir)
        input_path = workspace / f"input{source_suffix}"
        output_dir = workspace / "out"
        profile_dir = workspace / "profile"
        input_path.write_bytes(content)
        output_dir.mkdir()
        profile_dir.mkdir()

        command = [
            soffice,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--nolockcheck",
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--convert-to",
            convert_to,
            "--outdir",
            str(output_dir),
            str(input_path),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=settings.document_conversion_timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise DocumentConversionError(
                f"document conversion timed out after {settings.document_conversion_timeout_seconds} seconds"
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise DocumentConversionError(detail or "document conversion failed")

        output_path = output_dir / f"{input_path.stem}{target_suffix}"
        if not output_path.exists():
            candidates = sorted(output_dir.glob(f"*{target_suffix}"))
            if candidates:
                output_path = candidates[0]
        if not output_path.exists():
            detail = (completed.stderr or completed.stdout or "").strip()
            raise DocumentConversionError(detail or f"document conversion did not produce {target_suffix}")
        return output_path.read_bytes()


def _normalize_suffix(value: str) -> str:
    suffix = value.lower().strip()
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    return suffix


def _resolve_soffice_binary(configured: str) -> str:
    if not configured.strip():
        raise DocumentConverterUnavailableError("SOFFICE_BINARY is empty")
    configured = configured.strip()
    if Path(configured).is_absolute() or any(separator in configured for separator in ("/", "\\")):
        if Path(configured).exists():
            return configured
        raise DocumentConverterUnavailableError(f"LibreOffice executable not found: {configured}")
    resolved = shutil.which(configured)
    if resolved:
        return resolved
    raise DocumentConverterUnavailableError("LibreOffice soffice executable was not found")
