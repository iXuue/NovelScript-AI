import json
from typing import Any

from sqlalchemy.orm import Session

from app.domain.artifacts import ProjectStage
from app.models.project import Project
from app.models.runtime import ConversationMessageRecord
from app.models.scene_plan import ScenePlan
from app.models.script import ScriptContentBlock, ScriptVersion
from app.models.style import StyleProfile
from app.services.context_budget_service import generate_with_context_log, truncate_text
from app.services.feedback_plan_cache_service import (
    current_artifact_fingerprint,
    feedback_plan_to_dict,
    find_cached_feedback_plan,
    get_feedback_plan,
    normalize_target,
    stage_for_target,
    store_feedback_plan,
)
from app.services.llm_provider import LLMProvider
from app.services.local_snapshot_service import mirror_project_snapshot
from app.services.project_service import update_project_stage, update_project_stage_in_db
from app.services.run_service import create_project_run, update_run_status, update_run_step
from app.services.scene_plan_service import generate_scene_plan_artifact
from app.services.script_service import generate_script_from_confirmed_scene_plan, modify_script_from_feedback_plan
from app.services.store import STORE, now_utc, persistent_id


def _message_to_dict(message: ConversationMessageRecord) -> dict:
    return {
        "message_id": message.message_id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
    }


def list_primary_messages(project_id: str, db=None) -> dict:
    if db is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise KeyError(project_id)
        messages = (
            db.query(ConversationMessageRecord)
            .filter(
                ConversationMessageRecord.project_id == project_id,
                ConversationMessageRecord.conversation_id == project.primary_conversation_id,
            )
            .order_by(ConversationMessageRecord.created_at, ConversationMessageRecord.message_id)
            .all()
        )
        return {"conversation_id": project.primary_conversation_id, "messages": [_message_to_dict(message) for message in messages]}

    project = STORE.projects[project_id]
    return {
        "conversation_id": project["primary_conversation_id"],
        "messages": STORE.conversations.get(project_id, []),
    }


def send_message(project_id: str, content: str, db=None) -> dict:
    if db is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise KeyError(project_id)
        message = ConversationMessageRecord(
            message_id=persistent_id("msg"),
            project_id=project_id,
            conversation_id=project.primary_conversation_id,
            role="user",
            content=content,
            created_at=now_utc(),
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return _message_to_dict(message)

    project = STORE.projects[project_id]
    message = {
        "message_id": STORE.next_id("msg"),
        "conversation_id": project["primary_conversation_id"],
        "role": "user",
        "content": content,
        "created_at": now_utc(),
    }
    STORE.conversations.setdefault(project_id, []).append(message)
    return message


def create_feedback_plan(project_id: str, message: str, target: dict, db, llm_provider: LLMProvider | None) -> dict:
    if db is None:
        return modify_script(project_id, message, target, db)
    project = db.get(Project, project_id)
    if project is None:
        raise KeyError(project_id)
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to create a feedback plan")

    normalized_target = normalize_target(target)
    if normalized_target["type"] == "scene_plan" and _current_scene_plan_is_confirmed(db, project_id):
        raise PermissionError("scene_plan_confirmed")
    stage = stage_for_target(normalized_target)
    saved_message = send_message(project_id, message, db)
    artifact_fingerprint = current_artifact_fingerprint(db, project_id, stage)
    cached = find_cached_feedback_plan(
        db,
        project_id=project_id,
        stage=stage,
        target=normalized_target,
        user_feedback=message,
        artifact_fingerprint=artifact_fingerprint,
    )
    if cached is not None:
        payload = feedback_plan_to_dict(cached, cache_hit=True)
        payload["message"] = saved_message
        payload["run_id"] = None
        return payload

    run = create_project_run(project_id, "feedback_plan", "feedback_plan", ["feedback_plan"], db)
    run_id = run["run_id"]
    try:
        update_run_status(run_id, "running", db=db)
        update_run_step(project_id, run_id, "feedback_plan", "running", db=db)
        response = generate_with_context_log(
            llm_provider,
            task_type="feedback_plan",
            prompt=_feedback_plan_prompt(
                user_feedback=message,
                target=normalized_target,
                context=_feedback_plan_context(db, project_id, normalized_target),
            ),
            response_format="json",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="feedback_plan",
            source_item_count=1,
            included_item_count=1,
        )
        plan_payload = _validate_feedback_plan_payload(_load_json_object(response.text), normalized_target)
        entry = store_feedback_plan(
            db,
            project_id=project_id,
            message_id=saved_message["message_id"],
            stage=stage,
            target=normalized_target,
            user_feedback=message,
            artifact_fingerprint=artifact_fingerprint,
            modification_plan=plan_payload,
            source_requests=plan_payload["source_requests"],
        )
        update_run_step(project_id, run_id, "feedback_plan", "succeeded", "Feedback modification plan created", db=db)
        update_run_status(run_id, "succeeded", db=db)
        payload = feedback_plan_to_dict(entry, cache_hit=False)
        payload["message"] = saved_message
        payload["run_id"] = run_id
        return payload
    except Exception as exc:
        update_run_step(project_id, run_id, "feedback_plan", "failed", str(exc), db=db)
        update_run_status(run_id, "failed", str(exc), db=db)
        raise


def confirm_feedback_plan(project_id: str, feedback_plan_id: str, db, llm_provider: LLMProvider | None) -> dict:
    if db is None:
        raise KeyError("feedback_plan_not_found")
    entry = get_feedback_plan(db, project_id, feedback_plan_id)
    current_fingerprint = current_artifact_fingerprint(db, project_id, entry.stage)
    if current_fingerprint != entry.artifact_fingerprint:
        raise PermissionError("feedback_plan_stale")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to execute a feedback plan")

    plan = feedback_plan_to_dict(entry)
    if entry.stage == "scene_plan":
        run = create_project_run(project_id, "scene_plan_feedback", "scene_plan", ["scene_plan"], db)
        run_id = run["run_id"]
        try:
            update_run_status(run_id, "running", db=db)
            update_run_step(project_id, run_id, "scene_plan", "running", db=db)
            scene_plan = generate_scene_plan_artifact(db, project_id, llm_provider, run_id=run_id, feedback_plan=plan)
            mirror_project_snapshot(db, project_id)
            update_project_stage(project_id, ProjectStage.scene_plan_draft)
            update_project_stage_in_db(db, project_id, ProjectStage.scene_plan_draft)
            update_run_step(project_id, run_id, "scene_plan", "succeeded", "Scene Plan regenerated from feedback", db=db)
            update_run_status(run_id, "succeeded", db=db)
            return {
                "run_id": run_id,
                "status": "succeeded",
                "stage": "scene_plan",
                "scene_plan_id": scene_plan["scene_plan_id"],
            }
        except Exception as exc:
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, "scene_plan", "failed", str(exc), db=db)
            update_run_status(run_id, "failed", str(exc), db=db)
            raise

    run = create_project_run(project_id, "script_feedback", "script_generating", ["script_generation", "validation"], db)
    run_id = run["run_id"]
    try:
        update_run_status(run_id, "running", db=db)
        update_run_step(project_id, run_id, "script_generation", "running", db=db)
        if entry.target_type == "script":
            result = generate_script_from_confirmed_scene_plan(db, project_id, llm_provider, run_id=run_id, feedback_plan=plan)
        else:
            result = modify_script_from_feedback_plan(db, project_id, llm_provider, plan, run_id=run_id)
        mirror_project_snapshot(db, project_id)
        update_run_step(project_id, run_id, "script_generation", "succeeded", "Script generated from feedback", db=db)
        update_run_step(project_id, run_id, "validation", "succeeded", "Deterministic validation completed", db=db)
        update_run_status(run_id, "succeeded", db=db)
        result["run_id"] = run_id
        result["status"] = "succeeded"
        return result
    except Exception as exc:
        mirror_project_snapshot(db, project_id)
        update_run_step(project_id, run_id, "script_generation", "failed", str(exc), db=db)
        update_run_status(run_id, "failed", str(exc), db=db)
        raise


def modify_script(project_id: str, message: str, target: dict, db=None) -> dict:
    if target.get("type") in {"chapters", "script"}:
        send_message(project_id, message, db)
        run = create_project_run(project_id, "conversation_edit", "conversation_edit", ["conversation_edit", "validation"], db)
        return {"run_id": run["run_id"], "status": "running", "stage": "conversation_edit"}
    raise PermissionError("scene_plan_change_required")


def _feedback_plan_prompt(user_feedback: str, target: dict[str, Any], context: dict[str, Any]) -> str:
    return (
        "You are the Feedback Planning Worker for a novel-to-screenplay adaptation system.\n"
        "Create a concrete modification plan only. Do not rewrite the Scene Plan or screenplay yet.\n"
        "Return only one JSON object. No Markdown. No explanation.\n"
        "JSON schema: {\"intent\":\"regenerate_scene_plan|regenerate_script|modify_chapter\","
        "\"affected_scope\":{\"chapter_ids\":[],\"scene_ids\":[]},\"modification_plan\":[\"...\"],"
        "\"needs_source_text\":true,\"source_requests\":[{\"paragraph_ids\":[],\"scene_ids\":[],\"chapter_ids\":[],\"reason\":\"...\"}],"
        "\"user_confirmation_required\":true}\n"
        "Rules:\n"
        "- The user must confirm this plan before generation.\n"
        "- Do not ask for full source text unless it is needed to avoid factual drift.\n"
        "- If target.type is scene_plan, use intent regenerate_scene_plan.\n"
        "- If target.type is script, use intent regenerate_script.\n"
        "- If target.type is chapters, use intent modify_chapter and include all target chapter_ids.\n"
        "- Script-stage feedback can only modify screenplay text within the selected chapter range.\n"
        "- Once a Scene Plan is confirmed, do not propose adding, deleting, reordering, or relinking Scene Plan scenes.\n"
        "- Keep the plan faithful to the provided adaptation context.\n\n"
        f"user_feedback:\n{user_feedback}\n\n"
        f"target:\n{json.dumps(target, ensure_ascii=False)}\n\n"
        f"context_without_full_source_text:\n{json.dumps(context, ensure_ascii=False)}"
    )


def _feedback_plan_context(db: Session, project_id: str, target: dict[str, Any]) -> dict[str, Any]:
    style_profile = (
        db.query(StyleProfile)
        .filter(StyleProfile.project_id == project_id)
        .order_by(StyleProfile.created_at.desc())
        .first()
    )
    context: dict[str, Any] = {
        "style_profile": truncate_text(style_profile.profile_text, 1200, "") if style_profile is not None else None,
        "scene_plan": _current_scene_plan_summary(db, project_id),
        "script": _current_script_summary(db, project_id, target),
        "full_source_text_included": False,
    }
    return context


def _current_scene_plan_is_confirmed(db: Session, project_id: str) -> bool:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True))
        .order_by(ScenePlan.version_number.desc())
        .first()
    )
    return bool(scene_plan and scene_plan.confirmed)


def _current_scene_plan_summary(db: Session, project_id: str) -> dict[str, Any] | None:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True))
        .order_by(ScenePlan.version_number.desc())
        .first()
    )
    if scene_plan is None:
        return None
    return {
        "scene_plan_id": scene_plan.scene_plan_id,
        "confirmed": scene_plan.confirmed,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "source_chapter_ids": scene.source_chapter_ids,
                "source_paragraph_ids": scene.source_paragraph_ids,
                "location": scene.location,
                "time": scene.time,
                "characters": scene.characters,
                "scene_function": truncate_text(scene.scene_function, 240, ""),
                "core_conflict": truncate_text(scene.core_conflict, 240, ""),
            }
            for scene in sorted(scene_plan.scenes, key=lambda item: item.order)
        ],
    }


def _current_script_summary(db: Session, project_id: str, target: dict[str, Any]) -> dict[str, Any] | None:
    version = (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id, ScriptVersion.is_current.is_(True))
        .order_by(ScriptVersion.version_number.desc())
        .first()
    )
    if version is None:
        return None
    target_scene_ids = _target_scene_ids_for_summary(version, target)
    blocks_by_scene: dict[str, list[ScriptContentBlock]] = {}
    for block in sorted(version.content_blocks, key=lambda item: (item.scene_id, item.order)):
        if target_scene_ids is not None and block.scene_id not in target_scene_ids:
            continue
        blocks_by_scene.setdefault(block.scene_id, []).append(block)
    return {
        "script_version_id": version.script_version_id,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "source_chapter_ids": scene.source_chapter_ids,
                "scene_info": truncate_text(scene.scene_info, 240, ""),
                "blocks": [
                    {
                        "content_block_id": block.content_block_id,
                        "type": block.block_type,
                        "speaker": block.speaker,
                        "text": truncate_text(block.text, 180, ""),
                        "source_paragraph_ids": block.source_paragraph_ids,
                    }
                    for block in blocks_by_scene.get(scene.scene_id, [])[:8]
                ],
            }
            for scene in sorted(version.scenes, key=lambda item: item.order)
            if target_scene_ids is None or scene.scene_id in target_scene_ids
        ],
    }


def _target_scene_ids_for_summary(version: ScriptVersion, target: dict[str, Any]) -> set[str] | None:
    if target["type"] == "chapters":
        chapter_ids = set(target["chapter_ids"])
        return {scene.scene_id for scene in version.scenes if chapter_ids.intersection(scene.source_chapter_ids or [])}
    return None


def _load_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("feedback_plan returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("feedback_plan must return a JSON object")
    return payload


def _validate_feedback_plan_payload(payload: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    default_intent = {
        "scene_plan": "regenerate_scene_plan",
        "script": "regenerate_script",
        "chapters": "modify_chapter",
    }[target["type"]]
    intent = payload.get("intent") if isinstance(payload.get("intent"), str) else default_intent
    if intent not in {"regenerate_scene_plan", "regenerate_script", "modify_chapter"}:
        intent = default_intent
    affected_scope = payload.get("affected_scope") if isinstance(payload.get("affected_scope"), dict) else {}
    chapter_ids = _string_list(affected_scope.get("chapter_ids"))
    scene_ids = _string_list(affected_scope.get("scene_ids"))
    if target["type"] == "chapters":
        for chapter_id in target["chapter_ids"]:
            if chapter_id not in chapter_ids:
                chapter_ids.append(chapter_id)
    plan_items = _string_list(payload.get("modification_plan"))
    if not plan_items:
        plan_items = ["Revise the target artifact according to the user's feedback while preserving source facts."]
    source_requests = _source_requests(payload.get("source_requests"))
    return {
        "intent": intent,
        "affected_scope": {"chapter_ids": chapter_ids, "scene_ids": scene_ids},
        "modification_plan": plan_items,
        "needs_source_text": bool(payload.get("needs_source_text", bool(source_requests))),
        "source_requests": source_requests,
        "user_confirmation_required": True,
    }


def _source_requests(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    requests: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        requests.append(
            {
                "paragraph_ids": _string_list(item.get("paragraph_ids")),
                "scene_ids": _string_list(item.get("scene_ids")),
                "chapter_ids": _string_list(item.get("chapter_ids")),
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return requests


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
