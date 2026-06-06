import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.analysis import EvidenceItem
from app.models.export import ExportJob
from app.models.project import Project
from app.models.repair import RepairAttempt
from app.models.script import ScriptContentBlock, ScriptScene, ScriptSceneValidation, ScriptVersion
from app.models.scene_plan import ScenePlan, ScenePlanScene
from app.models.story import StoryBible
from app.models.style import StyleProfile
from app.services.context_budget_service import compact_lines, generate_with_context_log, rank_evidence_items, truncate_text
from app.services.export_service import to_yaml_preview
from app.services.llm_provider import LLMProvider
from app.services.project_service import update_project_stage, update_project_stage_in_db
from app.services.store import STORE, now_utc, persistent_id


BLOCK_TYPES = {"action", "dialogue", "narration", "transition", "note", "parenthetical", "voiceover", "description", "sound", "character", "shot"}
MAX_REPAIR_ATTEMPTS = 2


def generate_script_from_confirmed_scene_plan(db: Session, project_id: str, llm_provider: LLMProvider | None) -> dict:
    scene_plan = _confirmed_scene_plan(db, project_id)
    if scene_plan is None:
        raise PermissionError("scene_plan_not_confirmed")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to generate script")

    project = db.get(Project, project_id)
    evidence_items = _evidence_items(db, project_id)
    story_bible = _story_bible(db, project_id)
    style_profile = _style_profile(db, project_id)
    scenes = sorted(scene_plan.scenes, key=lambda scene: scene.order)
    generated_scenes = []
    model_names = []
    for scene in scenes:
        relevant_evidence_count = len([evidence for evidence in evidence_items if evidence.evidence_id in scene.source_evidence_ids])
        response = generate_with_context_log(
            llm_provider,
            task_type="script_generation",
            prompt=_script_scene_prompt(scene, evidence_items, story_bible, style_profile),
            response_format="json",
            db=db,
            project_id=project_id,
            step_type="script_generation",
            chunk_range={"scene_id": scene.scene_id, "scene_order": scene.order},
            source_item_count=relevant_evidence_count,
            included_item_count=min(relevant_evidence_count, 80),
        )
        model_names.append(response.model_name)
        generated_scenes.append(
            _validate_script_scene_payload(
                _load_json_object(response.text),
                scene=scene,
                evidence_ids={evidence.evidence_id for evidence in evidence_items},
            )
        )

    version = _replace_script_version(
        db,
        project_id=project_id,
        title=project.name if project is not None else project_id,
        scenes=generated_scenes,
        source=",".join(sorted(set(model_names))) if model_names else "unknown",
    )
    validations = _validate_and_store_script_scenes(db, version, scene_plan.scenes, evidence_items, style_profile, llm_provider)
    if any(not validation.passed for validation in validations):
        version.status = ArtifactStatus.failed
        version.updated_at = now_utc()
        db.commit()
        _mirror_script_to_store(project_id, version)
        update_project_stage(project_id, ProjectStage.script_generating)
        update_project_stage_in_db(db, project_id, ProjectStage.script_generating)
        raise PermissionError("script_scene_validation_failed")
    _mirror_script_to_store(project_id, version)
    update_project_stage(project_id, ProjectStage.script_ready)
    update_project_stage_in_db(db, project_id, ProjectStage.script_ready)
    return {"script_version_id": version.script_version_id, "status": "running", "stage": ProjectStage.script_generating}


def get_current_script_for_ui(db: Session | None, project_id: str) -> dict | None:
    if db is None:
        return STORE.script_ui.get(project_id)
    version = _current_script_version(db, project_id) or _latest_script_version(db, project_id)
    if version is None:
        return None
    return _script_ui(version)


def get_current_yaml_preview(db: Session | None, project_id: str) -> dict | None:
    if db is None:
        return STORE.yaml_previews.get(project_id)
    version = _current_script_version(db, project_id) or _latest_script_version(db, project_id)
    if version is None:
        return None
    return _yaml_preview(version)


def get_current_internal_script(db: Session | None, project_id: str) -> tuple[ScriptVersion, dict] | None:
    if db is None:
        internal = STORE.scripts.get(project_id)
        if internal is None:
            return None
        return None, internal  # 本地模式下 ScriptVersion ORM 对象不可用，返回 (None, dict)
    version = _current_script_version(db, project_id)
    if version is None:
        return None
    return version, _internal_script(version)


def repair_script_scene(db: Session, project_id: str, scene_id: str, llm_provider: LLMProvider | None) -> dict:
    version = _latest_script_version(db, project_id)
    if version is None:
        raise KeyError("script_missing")
    script_scene = next((scene for scene in version.scenes if scene.scene_id == scene_id), None)
    if script_scene is None:
        raise KeyError("script_scene_missing")
    validation = _latest_scene_validation(version, scene_id)
    if validation is None or validation.passed:
        raise PermissionError("script_scene_repair_not_required")
    if (
        _repair_attempt_count(
            db,
            project_id=project_id,
            artifact_type="script_scene",
            artifact_id=version.script_version_id,
            scene_id=scene_id,
        )
        >= MAX_REPAIR_ATTEMPTS
    ):
        raise PermissionError("repair_attempts_exceeded")
    scene_plan = _confirmed_scene_plan(db, project_id)
    if scene_plan is None:
        raise PermissionError("scene_plan_not_confirmed")
    scene_plan_scene = next((scene for scene in scene_plan.scenes if scene.scene_id == scene_id), None)
    if scene_plan_scene is None:
        raise KeyError("scene_plan_scene_missing")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to repair script scene")

    evidence_items = _evidence_items(db, project_id)
    style_profile = _style_profile(db, project_id)
    current_blocks = sorted([block for block in version.content_blocks if block.scene_id == scene_id], key=lambda block: block.order)
    relevant_evidence_count = len([evidence for evidence in evidence_items if evidence.evidence_id in scene_plan_scene.source_evidence_ids])
    response = generate_with_context_log(
        llm_provider,
        task_type="script_scene_repair",
        prompt=_script_scene_repair_prompt(scene_plan_scene, script_scene, current_blocks, validation, evidence_items, style_profile),
        response_format="json",
        db=db,
        project_id=project_id,
        step_type="script_scene_repair",
        chunk_range={"scene_id": scene_id},
        source_item_count=relevant_evidence_count + len(current_blocks),
        included_item_count=min(relevant_evidence_count, 80) + len(current_blocks),
    )
    repaired_scene = _validate_script_scene_payload(
        _load_json_object(response.text),
        scene=scene_plan_scene,
        evidence_ids={evidence.evidence_id for evidence in evidence_items},
    )
    _replace_script_scene_content(db, version, script_scene, repaired_scene)
    repaired_validation = _validate_and_store_one_script_scene(db, version, scene_plan_scene, script_scene, evidence_items, style_profile, llm_provider)
    all_passed = all(validation.passed for validation in version.scene_validations)
    version.status = ArtifactStatus.current if all_passed else ArtifactStatus.failed
    version.updated_at = now_utc()
    db.commit()
    _record_repair_attempt(
        db,
        project_id=project_id,
        artifact_type="script_scene",
        artifact_id=version.script_version_id,
        result_artifact_id=version.script_version_id,
        scene_id=scene_id,
        issues=validation.issues,
        status="success" if repaired_validation.passed else "failed",
        source=response.model_name,
    )
    _mirror_script_to_store(project_id, version)
    if all_passed:
        update_project_stage(project_id, ProjectStage.script_ready)
        update_project_stage_in_db(db, project_id, ProjectStage.script_ready)
    return {
        "script_version_id": version.script_version_id,
        "scene_id": scene_id,
        "validation": _validation_to_dict(repaired_validation),
    }


def _replace_script_version(db: Session, project_id: str, title: str, scenes: list[dict], source: str) -> ScriptVersion:
    previous_current = (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id, ScriptVersion.is_current.is_(True))
        .order_by(ScriptVersion.version_number.desc())
        .first()
    )
    for current in db.query(ScriptVersion).filter(ScriptVersion.project_id == project_id, ScriptVersion.is_current.is_(True)).all():
        current.is_current = False
        if current.status == ArtifactStatus.current:
            current.status = ArtifactStatus.historical
        current.stale_reason = "replaced_by_new_script"
        current.updated_at = now_utc()
    for export in db.query(ExportJob).filter(ExportJob.project_id == project_id, ExportJob.status == "succeeded").all():
        export.status = "stale"
    next_version_number = (
        db.query(ScriptVersion.version_number)
        .filter(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.version_number.desc())
        .first()
    )
    version_number = (next_version_number[0] if next_version_number else 0) + 1
    timestamp = now_utc()
    script_version = ScriptVersion(
        script_version_id=persistent_id("script_v"),
        project_id=project_id,
        version_number=version_number,
        is_current=True,
        parent_script_version_id=previous_current.script_version_id if previous_current is not None else None,
        stale_reason=None,
        status=ArtifactStatus.current,
        source=source,
        generated_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    script_version.scenes = [
        ScriptScene(
            script_version_id=script_version.script_version_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            order=index,
            title=scene["title"],
            source_chapter_ids=scene["source_chapter_ids"],
            scene_info=scene["scene_info"],
            characters=scene["characters"],
            scene_purpose=scene["scene_purpose"],
            core_conflict=scene["core_conflict"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        for index, scene in enumerate(scenes, start=1)
    ]
    blocks = []
    block_counter = 0
    for scene in scenes:
        for index, block in enumerate(scene["content_blocks"], start=1):
            block_counter += 1
            blocks.append(
                ScriptContentBlock(
                    script_version_id=script_version.script_version_id,
                    project_id=project_id,
                    scene_id=scene["scene_id"],
                    content_block_id=f"CB{block_counter:03d}",
                    order=index,
                    block_type=block["type"],
                    text=block["text"],
                    speaker=block["speaker"],
                    source_evidence_ids=block["source_evidence_ids"],
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
    script_version.content_blocks = blocks
    db.add(script_version)
    db.commit()
    db.refresh(script_version)
    script_version._generated_title = title
    return script_version


def _replace_script_scene_content(db: Session, version: ScriptVersion, script_scene: ScriptScene, repaired_scene: dict) -> None:
    script_scene.title = repaired_scene["title"]
    script_scene.source_chapter_ids = repaired_scene["source_chapter_ids"]
    script_scene.scene_info = repaired_scene["scene_info"]
    script_scene.characters = repaired_scene["characters"]
    script_scene.scene_purpose = repaired_scene["scene_purpose"]
    script_scene.core_conflict = repaired_scene["core_conflict"]
    script_scene.updated_at = now_utc()
    db.execute(
        delete(ScriptContentBlock).where(
            ScriptContentBlock.script_version_id == version.script_version_id,
            ScriptContentBlock.scene_id == script_scene.scene_id,
        )
    )
    used_block_ids = {
        row[0]
        for row in db.query(ScriptContentBlock.content_block_id)
        .filter(
            ScriptContentBlock.script_version_id == version.script_version_id,
            ScriptContentBlock.scene_id != script_scene.scene_id,
        )
        .all()
    }
    next_block_number = _next_content_block_number(used_block_ids)
    timestamp = now_utc()
    for index, block in enumerate(repaired_scene["content_blocks"], start=1):
        content_block_id = block["content_block_id"]
        if content_block_id in used_block_ids:
            content_block_id = f"CB{next_block_number:03d}"
            next_block_number += 1
        used_block_ids.add(content_block_id)
        db.add(
            ScriptContentBlock(
                script_version_id=version.script_version_id,
                project_id=version.project_id,
                scene_id=script_scene.scene_id,
                content_block_id=content_block_id,
                order=index,
                block_type=block["type"],
                text=block["text"],
                speaker=block["speaker"],
                source_evidence_ids=block["source_evidence_ids"],
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    db.flush()


def _next_content_block_number(used_block_ids: set[str]) -> int:
    numbers = [int(block_id[2:]) for block_id in used_block_ids if block_id.startswith("CB") and block_id[2:].isdigit()]
    return max(numbers, default=0) + 1


def _script_scene_prompt(
    scene: ScenePlanScene,
    evidence_items: list[EvidenceItem],
    story_bible: StoryBible | None,
    style_profile: StyleProfile | None,
) -> str:
    relevant_evidence = [evidence for evidence in evidence_items if evidence.evidence_id in scene.source_evidence_ids]
    return (
        "You are the Script Generation Worker. Generate screenplay content for exactly one confirmed scene.\n"
        "Return only one JSON object. No Markdown. No explanation.\n"
        "JSON schema: {\"scene_id\":\"S001\",\"title\":\"...\",\"scene_info\":\"...\","
        "\"characters\":[\"...\"],\"scene_purpose\":\"...\",\"core_conflict\":\"...\","
        "\"content_blocks\":["
        "{\"content_block_id\":\"CB001\",\"type\":\"action/dialogue/narration/transition/note\","
        "\"text\":\"...\",\"speaker\":null,\"source_evidence_ids\":[\"EV001\"]}]}\n"
        "Rules:\n"
        "- scene_id must match the input scene.\n"
        "- scene_info must summarize interior/exterior, location, and time.\n"
        "- characters, scene_purpose, and core_conflict must be copied or refined from the scene plan.\n"
        "- Preserve required plot, dialogue, visual elements, and foreshadowing from the scene plan.\n"
        "- Block types are only action, dialogue, narration, transition, and note.\n"
        "- For dialogue blocks, speaker must be the character name and cannot be empty. For non-dialogue blocks, speaker must be null.\n"
        "- Every content block must be traceable with source_evidence_ids when relevant.\n"
        "- Do not include internal notes or analysis in text.\n\n"
        f"scene_plan_scene:\n{_scene_block(scene)}\n\n"
        f"relevant_evidence:\n{_evidence_block(relevant_evidence)}\n\n"
        f"story_bible:\n{_story_bible_block(story_bible)}\n\n"
        f"style_profile:\n{truncate_text(style_profile.profile_text, 3000) if style_profile is not None else 'Use a neutral, concise screenplay style.'}"
    )


def _validate_and_store_script_scenes(
    db: Session,
    version: ScriptVersion,
    scene_plan_scenes: list[ScenePlanScene],
    evidence_items: list[EvidenceItem],
    style_profile: StyleProfile | None,
    llm_provider: LLMProvider,
) -> list[ScriptSceneValidation]:
    scene_plan_by_id = {scene.scene_id: scene for scene in scene_plan_scenes}
    script_blocks_by_scene: dict[str, list[ScriptContentBlock]] = {}
    for block in version.content_blocks:
        script_blocks_by_scene.setdefault(block.scene_id, []).append(block)
    validations = []
    timestamp = now_utc()
    for script_scene in sorted(version.scenes, key=lambda scene: scene.order):
        scene_plan_scene = scene_plan_by_id[script_scene.scene_id]
        validation = _build_script_scene_validation(
            version,
            script_scene,
            scene_plan_scene,
            sorted(script_blocks_by_scene.get(script_scene.scene_id, []), key=lambda block: block.order),
            evidence_items,
            style_profile,
            llm_provider,
            timestamp,
            db=db,
        )
        db.add(validation)
        validations.append(validation)
    db.commit()
    db.refresh(version)
    return validations


def _validate_and_store_one_script_scene(
    db: Session,
    version: ScriptVersion,
    scene_plan_scene: ScenePlanScene,
    script_scene: ScriptScene,
    evidence_items: list[EvidenceItem],
    style_profile: StyleProfile | None,
    llm_provider: LLMProvider,
) -> ScriptSceneValidation:
    db.execute(
        delete(ScriptSceneValidation).where(
            ScriptSceneValidation.script_version_id == version.script_version_id,
            ScriptSceneValidation.scene_id == script_scene.scene_id,
        )
    )
    blocks = (
        db.query(ScriptContentBlock)
        .filter(
            ScriptContentBlock.script_version_id == version.script_version_id,
            ScriptContentBlock.scene_id == script_scene.scene_id,
        )
        .order_by(ScriptContentBlock.order)
        .all()
    )
    validation = _build_script_scene_validation(
        version,
        script_scene,
        scene_plan_scene,
        blocks,
        evidence_items,
        style_profile,
        llm_provider,
        now_utc(),
        db=db,
    )
    db.add(validation)
    db.commit()
    db.refresh(version)
    return validation


def _build_script_scene_validation(
    version: ScriptVersion,
    script_scene: ScriptScene,
    scene_plan_scene: ScenePlanScene,
    content_blocks: list[ScriptContentBlock],
    evidence_items: list[EvidenceItem],
    style_profile: StyleProfile | None,
    llm_provider: LLMProvider,
    timestamp,
    db=None,
) -> ScriptSceneValidation:
    relevant_evidence_count = len([evidence for evidence in evidence_items if evidence.evidence_id in scene_plan_scene.source_evidence_ids])
    response = generate_with_context_log(
        llm_provider,
        task_type="script_scene_validation",
        prompt=_script_scene_validation_prompt(
            scene_plan_scene,
            script_scene,
            content_blocks,
            evidence_items,
            style_profile,
        ),
        response_format="json",
        db=db,
        project_id=version.project_id,
        step_type="script_scene_validation",
        chunk_range={"scene_id": script_scene.scene_id},
        source_item_count=relevant_evidence_count + len(content_blocks),
        included_item_count=min(relevant_evidence_count, 80) + len(content_blocks),
    )
    payload = _validate_script_scene_validation_payload(_load_json_object(response.text))
    return ScriptSceneValidation(
        script_version_id=version.script_version_id,
        project_id=version.project_id,
        scene_id=script_scene.scene_id,
        passed=payload["passed"],
        issues=payload["issues"],
        suggestions=payload["suggestions"],
        coverage=payload["coverage"],
        source=response.model_name,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _script_scene_validation_prompt(
    scene_plan_scene: ScenePlanScene,
    script_scene: ScriptScene,
    content_blocks: list[ScriptContentBlock],
    evidence_items: list[EvidenceItem],
    style_profile: StyleProfile | None,
) -> str:
    relevant_evidence = [evidence for evidence in evidence_items if evidence.evidence_id in scene_plan_scene.source_evidence_ids]
    return (
        "You are the Script Scene Validator. Validate one generated screenplay scene against its confirmed Scene Plan.\n"
        "Return only one JSON object. No Markdown. No explanation.\n"
        "JSON schema: {\"passed\":true,\"issues\":[],\"suggestions\":[],"
        "\"coverage\":{\"must_cover_plot\":[],\"must_keep_dialogue\":[],"
        "\"must_keep_visual_elements\":[],\"must_keep_foreshadowing\":[]}}\n"
        "Validation checklist:\n"
        "- Required plot beats are present in screenplay content blocks.\n"
        "- Required dialogue, visual elements, and foreshadowing are preserved.\n"
        "- Dialogue blocks have speakers, block types are valid, and evidence references are coherent.\n"
        "- The scene reads as filmable screenplay content, not novel summary.\n"
        "- Style follows the style profile.\n\n"
        f"scene_plan_scene:\n{_scene_block(scene_plan_scene)}\n\n"
        f"script_scene:\n{_script_scene_block(script_scene)}\n\n"
        f"content_blocks:\n{_script_block(content_blocks)}\n\n"
        f"relevant_evidence:\n{_evidence_block(relevant_evidence)}\n\n"
        f"style_profile:\n{truncate_text(style_profile.profile_text, 3000) if style_profile is not None else 'Use a neutral, concise screenplay style.'}"
    )


def _script_scene_repair_prompt(
    scene_plan_scene: ScenePlanScene,
    script_scene: ScriptScene,
    content_blocks: list[ScriptContentBlock],
    validation: ScriptSceneValidation,
    evidence_items: list[EvidenceItem],
    style_profile: StyleProfile | None,
) -> str:
    relevant_evidence = [evidence for evidence in evidence_items if evidence.evidence_id in scene_plan_scene.source_evidence_ids]
    return (
        "You are the Script Scene Repair Worker. Repair exactly one generated screenplay scene according to validation issues.\n"
        "Return the full repaired scene as one JSON object. No Markdown. No explanation.\n"
        "Use the same schema as script_generation for one scene.\n"
        "Rules:\n"
        "- Preserve valid content blocks when possible.\n"
        "- Fix only issues identified by validation unless required for consistency.\n"
        "- Keep block types limited to action, dialogue, narration, transition, note.\n"
        "- Dialogue blocks must include speaker.\n\n"
        f"validation_issues:\n{json.dumps(validation.issues, ensure_ascii=False)}\n\n"
        f"validation_suggestions:\n{json.dumps(validation.suggestions, ensure_ascii=False)}\n\n"
        f"scene_plan_scene:\n{_scene_block(scene_plan_scene)}\n\n"
        f"script_scene:\n{_script_scene_block(script_scene)}\n\n"
        f"content_blocks:\n{_script_block(content_blocks)}\n\n"
        f"relevant_evidence:\n{_evidence_block(relevant_evidence)}\n\n"
        f"style_profile:\n{truncate_text(style_profile.profile_text, 3000) if style_profile is not None else 'Use a neutral, concise screenplay style.'}"
    )


def _scene_block(scene: ScenePlanScene) -> str:
    return json.dumps(
        {
            "scene_id": scene.scene_id,
            "title": scene.title,
            "source_chapter_ids": scene.source_chapter_ids,
            "source_evidence_ids": scene.source_evidence_ids,
            "interior_exterior": scene.interior_exterior,
            "location": scene.location,
            "time": scene.time,
            "characters": scene.characters,
            "must_cover_plot": scene.must_cover_plot,
            "must_keep_dialogue": scene.must_keep_dialogue,
            "must_keep_visual_elements": scene.must_keep_visual_elements,
            "must_keep_foreshadowing": scene.must_keep_foreshadowing,
            "scene_function": scene.scene_function,
            "core_conflict": scene.core_conflict,
            "adaptation_note": scene.adaptation_note,
        },
        ensure_ascii=False,
    )


def _script_scene_block(scene: ScriptScene) -> str:
    return json.dumps(
        {
            "scene_id": scene.scene_id,
            "title": scene.title,
            "source_chapter_ids": scene.source_chapter_ids,
            "scene_info": scene.scene_info,
            "characters": scene.characters,
            "scene_purpose": scene.scene_purpose,
            "core_conflict": scene.core_conflict,
        },
        ensure_ascii=False,
    )


def _script_block(content_blocks: list[ScriptContentBlock]) -> str:
    return "\n".join(
        json.dumps(
            {
                "content_block_id": block.content_block_id,
                "type": block.block_type,
                "text": block.text,
                "speaker": block.speaker,
                "source_evidence_ids": block.source_evidence_ids,
            },
            ensure_ascii=False,
        )
        for block in content_blocks
    )


def _evidence_block(evidence_items: list[EvidenceItem]) -> str:
    ranked = rank_evidence_items(evidence_items)
    return compact_lines(
        (
        json.dumps(
            {
                "evidence_id": evidence.evidence_id,
                "chapter_id": evidence.chapter_id,
                "paragraph_ids": evidence.paragraph_ids or ([evidence.paragraph_id] if evidence.paragraph_id else []),
                "quote": truncate_text(evidence.quote, 300, ""),
                "explanation": truncate_text(evidence.explanation, 600),
                "must_keep": evidence.must_keep,
            },
            ensure_ascii=False,
        )
        for evidence in ranked
        ),
        6000,
    )


def _story_bible_block(story_bible: StoryBible | None) -> str:
    if story_bible is None:
        return "{}"
    return json.dumps(
        {
            "title": story_bible.title,
            "tone": story_bible.tone,
            "main_characters": story_bible.main_characters,
            "relationships": story_bible.relationships,
            "locations": story_bible.locations,
            "central_conflict": truncate_text(story_bible.central_conflict, 800),
        },
        ensure_ascii=False,
    )


def _confirmed_scene_plan(db: Session, project_id: str) -> ScenePlan | None:
    return (
        db.query(ScenePlan)
        .filter(
            ScenePlan.project_id == project_id,
            ScenePlan.status == ArtifactStatus.current,
            ScenePlan.is_current.is_(True),
            ScenePlan.confirmed.is_(True),
        )
        .one_or_none()
    )


def _current_script_version(db: Session, project_id: str) -> ScriptVersion | None:
    return (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id, ScriptVersion.status == ArtifactStatus.current, ScriptVersion.is_current.is_(True))
        .one_or_none()
    )


def _latest_script_version(db: Session, project_id: str) -> ScriptVersion | None:
    return (
        db.query(ScriptVersion)
        .filter(ScriptVersion.project_id == project_id)
        .order_by(ScriptVersion.generated_at.desc())
        .first()
    )


def _latest_scene_validation(version: ScriptVersion, scene_id: str) -> ScriptSceneValidation | None:
    validations = sorted(
        [validation for validation in version.scene_validations if validation.scene_id == scene_id],
        key=lambda validation: validation.created_at,
        reverse=True,
    )
    return validations[0] if validations else None


def _evidence_items(db: Session, project_id: str) -> list[EvidenceItem]:
    return (
        db.query(EvidenceItem)
        .filter(EvidenceItem.project_id == project_id)
        .order_by(EvidenceItem.evidence_id)
        .all()
    )


def _story_bible(db: Session, project_id: str) -> StoryBible | None:
    return db.query(StoryBible).filter(StoryBible.project_id == project_id).one_or_none()


def _style_profile(db: Session, project_id: str) -> StyleProfile | None:
    return db.query(StyleProfile).filter(StyleProfile.project_id == project_id).one_or_none()


def _load_json_object(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("script_generation provider returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("script_generation provider response must be a JSON object")
    return payload


def _validate_script_scene_validation_payload(payload: dict) -> dict:
    passed = payload.get("passed")
    issues = payload.get("issues")
    suggestions = payload.get("suggestions")
    coverage = payload.get("coverage")
    if not isinstance(passed, bool):
        raise RuntimeError("script_scene_validation field passed must be a boolean")
    if not isinstance(issues, list):
        raise RuntimeError("script_scene_validation field issues must be a list")
    if not isinstance(suggestions, list):
        raise RuntimeError("script_scene_validation field suggestions must be a list")
    if not isinstance(coverage, dict):
        raise RuntimeError("script_scene_validation field coverage must be an object")
    return {"passed": passed, "issues": issues, "suggestions": suggestions, "coverage": coverage}


def _validate_script_scene_payload(payload: dict, scene: ScenePlanScene, evidence_ids: set[str]) -> dict:
    if payload.get("scene_id") != scene.scene_id:
        raise RuntimeError("script_generation scene_id must match scene plan")
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        raise RuntimeError("script_generation title must be a non-empty string")
    scene_info = payload.get("scene_info", _default_scene_info(scene))
    characters = payload.get("characters", scene.characters)
    scene_purpose = payload.get("scene_purpose", scene.scene_function)
    core_conflict = payload.get("core_conflict", scene.core_conflict)
    if not isinstance(scene_info, str) or not scene_info.strip():
        raise RuntimeError("script_generation scene_info must be a non-empty string")
    if not isinstance(characters, list):
        raise RuntimeError("script_generation characters must be a list")
    if not isinstance(scene_purpose, str) or not scene_purpose.strip():
        raise RuntimeError("script_generation scene_purpose must be a non-empty string")
    if not isinstance(core_conflict, str) or not core_conflict.strip():
        raise RuntimeError("script_generation core_conflict must be a non-empty string")
    blocks = payload.get("content_blocks")
    if not isinstance(blocks, list) or not blocks:
        raise RuntimeError("script_generation content_blocks must be a non-empty list")
    validated_blocks = []
    seen_block_ids: set[str] = set()
    for expected_order, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            raise RuntimeError("script_generation content block must be a JSON object")
        content_block_id = block.get("content_block_id")
        block_type = block.get("type")
        text = block.get("text")
        speaker = block.get("speaker")
        source_evidence_ids = block.get("source_evidence_ids")
        if not isinstance(content_block_id, str) or not content_block_id.strip():
            raise RuntimeError("script_generation content_block_id must be a non-empty string")
        if content_block_id in seen_block_ids:
            raise RuntimeError("script_generation content_block_id must be unique")
        if not isinstance(block_type, str) or block_type not in BLOCK_TYPES:
            raise RuntimeError("script_generation block type is invalid")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("script_generation block text must be a non-empty string")
        if block_type == "dialogue" and (not isinstance(speaker, str) or not speaker.strip()):
            raise RuntimeError("script_generation dialogue block requires speaker")
        if block_type != "dialogue" and speaker is not None:
            raise RuntimeError("script_generation non-dialogue block speaker must be null")
        if speaker is not None and not isinstance(speaker, str):
            raise RuntimeError("script_generation speaker must be null or a string")
        if not isinstance(source_evidence_ids, list):
            raise RuntimeError("script_generation source_evidence_ids must be a list")
        unknown_evidence = set(source_evidence_ids) - evidence_ids
        if unknown_evidence:
            raise RuntimeError(f"script_generation references unknown evidence: {sorted(unknown_evidence)}")
        seen_block_ids.add(content_block_id)
        validated_blocks.append(
            {
                "content_block_id": content_block_id.strip(),
                "order": expected_order,
                "type": block_type,
                "text": text.strip(),
                "speaker": speaker.strip() if isinstance(speaker, str) else None,
                "source_evidence_ids": source_evidence_ids,
            }
        )
    return {
        "scene_id": scene.scene_id,
        "title": title.strip(),
        "source_chapter_ids": scene.source_chapter_ids,
        "scene_info": scene_info.strip(),
        "characters": characters,
        "scene_purpose": scene_purpose.strip(),
        "core_conflict": core_conflict.strip(),
        "content_blocks": validated_blocks,
    }


def _default_scene_info(scene: ScenePlanScene) -> str:
    interior_exterior = getattr(scene, "interior_exterior", "")
    location = getattr(scene, "location", "")
    time = getattr(scene, "time", "")
    parts = [part for part in [interior_exterior, location, time] if part]
    return " / ".join(parts) if parts else scene.title


def _internal_script(version: ScriptVersion) -> dict:
    project = version.project
    title = getattr(version, "_generated_title", None) or (project.name if project is not None else version.project_id)
    blocks_by_scene: dict[str, list[ScriptContentBlock]] = {}
    for block in sorted(version.content_blocks, key=lambda item: (item.scene_id, item.order)):
        blocks_by_scene.setdefault(block.scene_id, []).append(block)
    return {
        "title": title,
        "characters": [],
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "source_chapter_ids": scene.source_chapter_ids,
                "scene_info": scene.scene_info,
                "characters": scene.characters,
                "scene_purpose": scene.scene_purpose,
                "core_conflict": scene.core_conflict,
                "content_blocks": [
                    {
                        "content_block_id": block.content_block_id,
                        "type": block.block_type,
                        "text": block.text,
                        "speaker": block.speaker,
                        "source_evidence_ids": block.source_evidence_ids,
                    }
                    for block in blocks_by_scene.get(scene.scene_id, [])
                ],
            }
            for scene in sorted(version.scenes, key=lambda item: item.order)
        ],
    }


def _script_ui(version: ScriptVersion) -> dict:
    validations_by_scene = {validation.scene_id: validation for validation in version.scene_validations}
    return {
        "script_version_id": version.script_version_id,
        "status": version.status,
        "generated_at": version.generated_at,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "title": scene.title,
                "source_chapter_ids": scene.source_chapter_ids,
                "scene_info": scene.scene_info,
                "characters": scene.characters,
                "scene_purpose": scene.scene_purpose,
                "core_conflict": scene.core_conflict,
                "validation": _validation_to_dict(validations_by_scene.get(scene.scene_id)),
            }
            for scene in sorted(version.scenes, key=lambda item: item.order)
        ],
        "content_blocks": [
            {
                "content_block_id": block.content_block_id,
                "scene_id": block.scene_id,
                "block_type": block.block_type,
                "display_label": f"{block.scene_id} {block.block_type} {block.order}",
                "text": block.text,
                "speaker": block.speaker,
                "source_evidence_ids": block.source_evidence_ids,
            }
            for block in sorted(version.content_blocks, key=lambda item: (item.scene_id, item.order))
        ],
    }


def _yaml_preview(version: ScriptVersion) -> dict:
    return {
        "script_version_id": version.script_version_id,
        "status": version.status,
        "yaml": to_yaml_preview(_internal_script(version)),
        "generated_at": version.generated_at,
    }


def _mirror_script_to_store(project_id: str, version: ScriptVersion) -> None:
    internal = _internal_script(version)
    STORE.scripts[project_id] = {
        "script_version_id": version.script_version_id,
        "status": version.status,
        "generated_at": version.generated_at,
        "internal": internal,
    }
    STORE.script_ui[project_id] = _script_ui(version)
    STORE.yaml_previews[project_id] = _yaml_preview(version)


def _validation_to_dict(validation: ScriptSceneValidation | None) -> dict | None:
    if validation is None:
        return None
    return {
        "passed": validation.passed,
        "issues": validation.issues,
        "suggestions": validation.suggestions,
        "coverage": validation.coverage,
        "source": validation.source,
        "created_at": validation.created_at,
    }


def _record_repair_attempt(
    db: Session,
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    result_artifact_id: str | None,
    scene_id: str | None,
    issues: list,
    status: str,
    source: str,
) -> RepairAttempt:
    attempt_no = (
        db.query(RepairAttempt)
        .filter(
            RepairAttempt.project_id == project_id,
            RepairAttempt.artifact_type == artifact_type,
            RepairAttempt.artifact_id == artifact_id,
            RepairAttempt.scene_id == scene_id,
        )
        .count()
        + 1
    )
    attempt = RepairAttempt(
        project_id=project_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        result_artifact_id=result_artifact_id,
        scene_id=scene_id,
        attempt_no=attempt_no,
        issues=issues,
        status=status,
        source=source,
        created_at=now_utc(),
    )
    db.add(attempt)
    db.commit()
    return attempt


def _repair_attempt_count(
    db: Session,
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    scene_id: str | None,
) -> int:
    return (
        db.query(RepairAttempt)
        .filter(
            RepairAttempt.project_id == project_id,
            RepairAttempt.artifact_type == artifact_type,
            RepairAttempt.artifact_id == artifact_id,
            RepairAttempt.scene_id == scene_id,
        )
        .count()
    )
