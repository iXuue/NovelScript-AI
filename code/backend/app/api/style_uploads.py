from fastapi import APIRouter, Request

from app.api.errors import api_error
from app.services.input_adapter import normalize_to_markdown, parse_multipart_file
from app.services.project_service import require_project
from app.services.style_service import upload_style_reference

router = APIRouter()


@router.post("/projects/{project_id}/style-reference-uploads")
async def upload_style_reference_endpoint(project_id: str, request: Request):
    try:
        require_project(project_id)
        payload = parse_multipart_file(await request.body(), request.headers.get("content-type", ""))
        normalize_to_markdown(payload.filename, payload.content)
        return upload_style_reference(project_id, payload.filename)
    except KeyError:
        raise api_error(404, "project_not_found", "Project not found")
    except PermissionError:
        raise api_error(409, "style_source_locked", "Style source is locked after Scene Plan confirmation")
    except ValueError as exc:
        code = "unsupported_media_type" if "unsupported" in str(exc) or ".doc" in str(exc) else "validation_error"
        raise api_error(415 if code == "unsupported_media_type" else 400, code, str(exc))

