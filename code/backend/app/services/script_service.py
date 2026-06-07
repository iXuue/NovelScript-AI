import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.chapter import Paragraph
from app.models.export import ExportJob
from app.models.project import Project
from app.models.repair import RepairAttempt
from app.models.script import ScriptContentBlock, ScriptScene, ScriptSceneValidation, ScriptVersion
from app.models.scene_plan import ScenePlan, ScenePlanScene
from app.models.style import StyleProfile
from app.services.context_budget_service import compact_lines, generate_with_context_log, truncate_text
from app.services.export_service import to_yaml_preview
from app.services.llm_provider import LLMProvider
from app.services.project_service import update_project_stage, update_project_stage_in_db
from app.services.source_id_service import normalize_paragraph_ids
from app.services.store import STORE, now_utc, persistent_id


BLOCK_TYPES = {"action", "dialogue", "narration", "transition", "note", "parenthetical", "voiceover", "description", "sound", "character", "shot"}
MAX_REPAIR_ATTEMPTS = 2


def generate_script_from_confirmed_scene_plan(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None,
    run_id: str | None = None,
    feedback_plan: dict | None = None,
) -> dict:
    scene_plan = _confirmed_scene_plan(db, project_id)
    if scene_plan is None:
        raise PermissionError("scene_plan_not_confirmed")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to generate script")

    project = db.get(Project, project_id)
    paragraphs_by_id = _paragraphs_by_id(db, project_id)
    style_profile = _style_profile(db, project_id)
    scenes = sorted(scene_plan.scenes, key=lambda scene: scene.order)
    generated_scenes = []
    model_names = []
    for scene in scenes:
        relevant_paragraphs = _source_paragraphs_for_scene(scene, paragraphs_by_id)
        response = generate_with_context_log(
            llm_provider,
            task_type="script_generation",
            prompt=_script_scene_prompt(scene, relevant_paragraphs, style_profile, feedback_plan=feedback_plan),
            response_format="json",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="script_generation",
            chunk_range={"scene_id": scene.scene_id, "scene_order": scene.order},
            source_item_count=len(relevant_paragraphs),
            included_item_count=len(relevant_paragraphs),
        )
        model_names.append(response.model_name)
        generated_scenes.append(
            _validate_script_scene_payload(
                _load_json_object(response.text),
                scene=scene,
                paragraph_ids=set(paragraphs_by_id),
            )
        )

    version = _replace_script_version(
        db,
        project_id=project_id,
        title=project.name if project is not None else project_id,
        scenes=generated_scenes,
        source=",".join(sorted(set(model_names))) if model_names else "unknown",
    )
    validations = _validate_and_store_script_scenes(db, version, scene_plan.scenes, paragraphs_by_id)
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

    paragraphs_by_id = _paragraphs_by_id(db, project_id)
    style_profile = _style_profile(db, project_id)
    current_blocks = sorted([block for block in version.content_blocks if block.scene_id == scene_id], key=lambda block: block.order)
    relevant_paragraphs = _source_paragraphs_for_scene(scene_plan_scene, paragraphs_by_id)
    response = generate_with_context_log(
        llm_provider,
        task_type="script_scene_repair",
        prompt=_script_scene_repair_prompt(scene_plan_scene, script_scene, current_blocks, validation, relevant_paragraphs, style_profile),
        response_format="json",
        db=db,
        project_id=project_id,
        step_type="script_scene_repair",
        chunk_range={"scene_id": scene_id},
        source_item_count=len(relevant_paragraphs) + len(current_blocks),
        included_item_count=len(relevant_paragraphs) + len(current_blocks),
    )
    repaired_scene = _validate_script_scene_payload(
        _load_json_object(response.text),
        scene=scene_plan_scene,
        paragraph_ids=set(paragraphs_by_id),
    )
    _replace_script_scene_content(db, version, script_scene, repaired_scene)
    repaired_validation = _validate_and_store_one_script_scene(db, version, scene_plan_scene, script_scene, paragraphs_by_id)
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


def modify_script_from_feedback_plan(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None,
    feedback_plan: dict,
    run_id: str | None = None,
) -> dict:
    current_version = _current_script_version(db, project_id)
    if current_version is None:
        raise KeyError("script_missing")
    scene_plan = _confirmed_scene_plan(db, project_id)
    if scene_plan is None:
        raise PermissionError("scene_plan_not_confirmed")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to modify script")

    target_scene_ids = _target_scene_ids_from_feedback(scene_plan, feedback_plan)
    if not target_scene_ids:
        raise KeyError("script_target_scene_missing")

    project = db.get(Project, project_id)
    paragraphs_by_id = _paragraphs_by_id(db, project_id)
    style_profile = _style_profile(db, project_id)
    script_scenes_by_id = {scene.scene_id: scene for scene in current_version.scenes}
    blocks_by_scene: dict[str, list[ScriptContentBlock]] = {}
    for block in sorted(current_version.content_blocks, key=lambda item: (item.scene_id, item.order)):
        blocks_by_scene.setdefault(block.scene_id, []).append(block)

    generated_scenes: list[dict] = []
    model_names: list[str] = []
    for scene_plan_scene in sorted(scene_plan.scenes, key=lambda scene: scene.order):
        current_script_scene = script_scenes_by_id.get(scene_plan_scene.scene_id)
        current_blocks = blocks_by_scene.get(scene_plan_scene.scene_id, [])
        if scene_plan_scene.scene_id not in target_scene_ids:
            if current_script_scene is None:
                raise KeyError("script_scene_missing")
            generated_scenes.append(_script_scene_payload_from_existing(current_script_scene, current_blocks))
            continue
        relevant_paragraphs = _source_paragraphs_for_scene(scene_plan_scene, paragraphs_by_id)
        response = generate_with_context_log(
            llm_provider,
            task_type="script_generation",
            prompt=_script_scene_prompt(
                scene_plan_scene,
                relevant_paragraphs,
                style_profile,
                feedback_plan=feedback_plan,
                current_script_scene=current_script_scene,
                current_blocks=current_blocks,
            ),
            response_format="json",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="script_generation",
            chunk_range={"scene_id": scene_plan_scene.scene_id, "feedback_target": feedback_plan.get("target")},
            source_item_count=len(relevant_paragraphs) + len(current_blocks),
            included_item_count=len(relevant_paragraphs) + len(current_blocks),
        )
        model_names.append(response.model_name)
        generated_scenes.append(
            _validate_script_scene_payload(
                _load_json_object(response.text),
                scene=scene_plan_scene,
                paragraph_ids=set(paragraphs_by_id),
            )
        )

    version = _replace_script_version(
        db,
        project_id=project_id,
        title=project.name if project is not None else project_id,
        scenes=generated_scenes,
        source=",".join(sorted(set(model_names))) if model_names else current_version.source,
    )
    validations = _validate_and_store_script_scenes(db, version, scene_plan.scenes, paragraphs_by_id)
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
    return {
        "script_version_id": version.script_version_id,
        "status": "running",
        "stage": ProjectStage.script_generating,
        "target_scene_ids": sorted(target_scene_ids),
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
                    parenthetical=block.get("parenthetical"),
                    source_evidence_ids=block["source_evidence_ids"],
                    source_paragraph_ids=block["source_paragraph_ids"],
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
                parenthetical=block.get("parenthetical"),
                source_evidence_ids=block["source_evidence_ids"],
                source_paragraph_ids=block["source_paragraph_ids"],
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
    db.flush()


def _next_content_block_number(used_block_ids: set[str]) -> int:
    numbers = [int(block_id[2:]) for block_id in used_block_ids if block_id.startswith("CB") and block_id[2:].isdigit()]
    return max(numbers, default=0) + 1


def _target_scene_ids_from_feedback(scene_plan: ScenePlan, feedback_plan: dict) -> set[str]:
    target = feedback_plan.get("target") or {}
    target_type = target.get("type")
    if target_type == "chapters":
        chapter_ids = {str(chapter_id).strip() for chapter_id in target.get("chapter_ids") or [] if str(chapter_id).strip()}
        if not chapter_ids:
            return set()
        return {
            scene.scene_id
            for scene in scene_plan.scenes
            if chapter_ids.intersection(scene.source_chapter_ids or [])
        }
    affected_scope = feedback_plan.get("modification_plan", {}).get("affected_scope") if isinstance(feedback_plan.get("modification_plan"), dict) else {}
    chapter_ids = affected_scope.get("chapter_ids") if isinstance(affected_scope, dict) else []
    normalized_chapter_ids = {str(chapter_id).strip() for chapter_id in chapter_ids or [] if str(chapter_id).strip()}
    return {
        scene.scene_id
        for scene in scene_plan.scenes
        if normalized_chapter_ids.intersection(scene.source_chapter_ids or [])
    }


def _script_scene_payload_from_existing(script_scene: ScriptScene, content_blocks: list[ScriptContentBlock]) -> dict:
    return {
        "scene_id": script_scene.scene_id,
        "title": script_scene.title,
        "source_chapter_ids": script_scene.source_chapter_ids,
        "scene_info": script_scene.scene_info,
        "characters": script_scene.characters,
        "scene_purpose": script_scene.scene_purpose,
        "core_conflict": script_scene.core_conflict,
        "content_blocks": [
            {
                "content_block_id": block.content_block_id,
                "type": block.block_type,
                "text": block.text,
                "speaker": block.speaker,
                "source_evidence_ids": block.source_evidence_ids,
                "source_paragraph_ids": block.source_paragraph_ids,
            }
            for block in content_blocks
        ],
    }


def _script_scene_prompt(
    scene: ScenePlanScene,
    paragraphs: list[Paragraph],
    style_profile: StyleProfile | None,
    feedback_plan: dict | None = None,
    current_script_scene: ScriptScene | None = None,
    current_blocks: list[ScriptContentBlock] | None = None,
) -> str:
    feedback_text = ""
    if feedback_plan is not None:
        feedback_context = {
            "target": feedback_plan.get("target"),
            "user_feedback": feedback_plan.get("user_feedback"),
            "confirmed_modification_plan": feedback_plan.get("modification_plan"),
            "source_requests": feedback_plan.get("source_requests"),
        }
        feedback_text = (
            "\n\nconfirmed_feedback_plan:\n"
            f"{json.dumps(feedback_context, ensure_ascii=False)}"
        )
        if current_script_scene is not None:
            feedback_text += (
                "\n\ncurrent_script_scene:\n"
                f"{_script_scene_block(current_script_scene)}\n\n"
                "current_content_blocks:\n"
                f"{_script_block(current_blocks or [])}"
            )
    return (
        "你是剧本生成 Worker。请为已确认的单个场景生成剧本内容。\n"
        "所有描述性文本必须使用中文。JSON 的 key 也必须使用中文。只输出一个 JSON object，不要 Markdown，不要解释。\n"
        "JSON schema：{\"场景编号\":\"S001\",\"标题\":\"...\",\"场景信息\":\"...\","
        "\"人物\":[\"...\"],\"场景目的\":\"...\",\"核心冲突\":\"...\","
        "\"内容块\":["
        "{\"内容块编号\":\"CB001\",\"类型\":\"action\",\"文本\":\"她站在门口，雨水从屋檐滴落。\",\"说话人\":null,\"表演指示\":null,\"来源段落编号\":[\"CH001_P001\"],\"来源证据编号\":[]},"
        "{\"内容块编号\":\"CB002\",\"类型\":\"dialogue\",\"文本\":\"我回来了。\",\"说话人\":\"林雨\",\"表演指示\":\"低声\",\"来源段落编号\":[\"CH001_P002\"],\"来源证据编号\":[]}]}\n"
        "规则：\n"
        "- 场景编号 必须与输入场景一致。\n"
        "- 标题、文本、场景信息、场景目的、核心冲突等所有描述字段必须使用中文撰写。\n"
        "- 场景信息 概括内外景、地点和时间，格式如\"外景 / 旧宅门口 / 夜\"。\n"
        "- 人物 列出出场人物中文名；场景目的 描述场景结构功能；核心冲突 描述核心冲突。\n"
        "- 从 Scene Plan 中保留必要的 must_cover_plot、must_keep_dialogue、must_keep_visual_elements、must_keep_foreshadowing。\n"
        "- 内容块 的 类型 只能是 action（动作描写）、dialogue（对白）、narration（旁白）、transition（转场）、note（注释）。\n"
        "- 对白块的 说话人 必须填写角色中文名且不能为空。非对白块的 说话人 必须为 null。\n"
        "- 对白块必须填写 表演指示（如 低声、颤抖、冷笑、激动、平静），描述台词的语调、情绪、音量和身体状态。只有当情绪明显且中性时才可省略。非对白块 表演指示 必须为 null。\n"
        "- 如果对白 说话人 不明确，使用简洁的描述性称呼，如 围观者、人群、旁白，或原文中最接近的角色名。绝不能省略对白的 说话人。\n"
        "- 每个内容块必须引用 来源段落编号，且不能为空。如果一个块浓缩了多个原文段落，需要引用所有相关段落 ID。\n"
        "- 来源证据编号 为兼容字段，始终返回空数组。\n"
        "- 如果提供了 confirmed_feedback_plan，仅修改指定范围内的剧本文本，保留原文事实。\n"
        "- Scene Plan 已确认，不得改变场景编号、场景顺序、来源章节或来源段落。\n"
        "- 文本 中不得包含内部分析或注释。\n\n"
        f"scene_plan_scene:\n{_scene_block(scene)}\n\n"
        f"source_paragraphs:\n{_paragraph_block(paragraphs)}\n\n"
        f"style_profile:\n{truncate_text(style_profile.profile_text, 3000) if style_profile is not None else '使用中性、简洁的剧本风格。'}"
        f"{feedback_text}"
    )


def _validate_and_store_script_scenes(
    db: Session,
    version: ScriptVersion,
    scene_plan_scenes: list[ScenePlanScene],
    paragraphs_by_id: dict[str, Paragraph],
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
            paragraphs_by_id,
            timestamp,
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
    paragraphs_by_id: dict[str, Paragraph],
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
        paragraphs_by_id,
        now_utc(),
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
    paragraphs_by_id: dict[str, Paragraph],
    timestamp,
) -> ScriptSceneValidation:
    issues = []
    suggestions = []
    scene_paragraph_ids = set(scene_plan_scene.source_paragraph_ids or [])
    known_paragraph_ids = set(paragraphs_by_id)
    if script_scene.scene_id != scene_plan_scene.scene_id:
        issues.append("script scene_id does not match scene plan scene_id")
    if script_scene.source_chapter_ids != scene_plan_scene.source_chapter_ids:
        issues.append("script source_chapter_ids do not match scene plan")
    if not content_blocks:
        issues.append("scene has no content blocks")
    covered_paragraph_ids: set[str] = set()
    for block in content_blocks:
        if block.block_type not in BLOCK_TYPES:
            issues.append(f"{block.content_block_id} has invalid block type")
        if not block.text or not block.text.strip():
            issues.append(f"{block.content_block_id} has empty text")
        if block.block_type == "dialogue" and (not block.speaker or not block.speaker.strip()):
            issues.append(f"{block.content_block_id} dialogue block is missing speaker")
        if block.block_type != "dialogue" and block.speaker is not None:
            issues.append(f"{block.content_block_id} non-dialogue block should not have speaker")
        if not block.source_paragraph_ids:
            issues.append(f"{block.content_block_id} has no source_paragraph_ids")
            continue
        unknown = set(block.source_paragraph_ids) - known_paragraph_ids
        if unknown:
            issues.append(f"{block.content_block_id} references unknown paragraphs: {sorted(unknown)}")
        outside_scene = set(block.source_paragraph_ids) - scene_paragraph_ids
        if outside_scene:
            issues.append(f"{block.content_block_id} references paragraphs outside scene plan: {sorted(outside_scene)}")
        covered_paragraph_ids.update(block.source_paragraph_ids)
    if scene_paragraph_ids and not covered_paragraph_ids:
        suggestions.append("content blocks should cite at least one source paragraph from the scene plan")
    payload = {
        "passed": not issues,
        "issues": issues,
        "suggestions": suggestions,
        "coverage": {
            "source_paragraph_ids": sorted(covered_paragraph_ids),
            "scene_source_paragraph_ids": sorted(scene_paragraph_ids),
        },
    }
    return ScriptSceneValidation(
        script_version_id=version.script_version_id,
        project_id=version.project_id,
        scene_id=script_scene.scene_id,
        passed=payload["passed"],
        issues=payload["issues"],
        suggestions=payload["suggestions"],
        coverage=payload["coverage"],
        source="deterministic",
        created_at=timestamp,
        updated_at=timestamp,
    )


def _script_scene_repair_prompt(
    scene_plan_scene: ScenePlanScene,
    script_scene: ScriptScene,
    content_blocks: list[ScriptContentBlock],
    validation: ScriptSceneValidation,
    paragraphs: list[Paragraph],
    style_profile: StyleProfile | None,
) -> str:
    return (
        "你是剧本场景修复 Worker。请根据校验问题修复已生成的单个剧本场景。\n"
        "所有描述性文本必须使用中文，JSON 的 key 也必须使用中文。返回完整的修复后场景，只输出一个 JSON object，不要 Markdown，不要解释。\n"
        "使用与 script_generation 相同的中文 key schema。\n"
        "规则：\n"
        "- 尽量保留有效的 content_blocks。\n"
        "- 仅修复校验报告中指出的问题，除非一致性需要额外调整。\n"
        "- content_blocks 的 type 只能是 action（动作描写）、dialogue（对白）、narration（旁白）、transition（转场）、note（注释）。\n"
        "- 对白块必须包含 speaker（角色中文名）。\n"
        "- 对白块必须包含 parenthetical 表演指示。\n\n"
        f"validation_issues:\n{json.dumps(validation.issues, ensure_ascii=False)}\n\n"
        f"validation_suggestions:\n{json.dumps(validation.suggestions, ensure_ascii=False)}\n\n"
        f"scene_plan_scene:\n{_scene_block(scene_plan_scene)}\n\n"
        f"script_scene:\n{_script_scene_block(script_scene)}\n\n"
        f"content_blocks:\n{_script_block(content_blocks)}\n\n"
        f"source_paragraphs:\n{_paragraph_block(paragraphs)}\n\n"
        f"style_profile:\n{truncate_text(style_profile.profile_text, 3000) if style_profile is not None else '使用中性、简洁的剧本风格。'}"
    )


def _scene_block(scene: ScenePlanScene) -> str:
    return json.dumps(
        {
            "scene_id": scene.scene_id,
            "title": scene.title,
            "source_chapter_ids": scene.source_chapter_ids,
            "source_evidence_ids": scene.source_evidence_ids,
            "source_paragraph_ids": scene.source_paragraph_ids,
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
                "parenthetical": block.parenthetical,
                "source_evidence_ids": block.source_evidence_ids,
                "source_paragraph_ids": block.source_paragraph_ids,
            },
            ensure_ascii=False,
        )
        for block in content_blocks
    )


def _paragraph_block(paragraphs: list[Paragraph]) -> str:
    return compact_lines(
        (
        json.dumps(
            {
                "source_paragraph_id": paragraph.paragraph_id,
                "chapter_id": paragraph.chapter_id,
                "paragraph_id": paragraph.paragraph_id,
                "text": truncate_text(paragraph.text, 700, ""),
            },
            ensure_ascii=False,
        )
        for paragraph in paragraphs
        ),
        6000,
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


def _paragraphs_by_id(db: Session, project_id: str) -> dict[str, Paragraph]:
    paragraphs = (
        db.query(Paragraph)
        .filter(Paragraph.project_id == project_id)
        .order_by(Paragraph.chapter_id, Paragraph.order)
        .all()
    )
    return {paragraph.paragraph_id: paragraph for paragraph in paragraphs}


def _source_paragraphs_for_scene(scene: ScenePlanScene, paragraphs_by_id: dict[str, Paragraph]) -> list[Paragraph]:
    return [paragraphs_by_id[paragraph_id] for paragraph_id in scene.source_paragraph_ids if paragraph_id in paragraphs_by_id]


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


CHINESE_KEY_MAP = {
    "场景编号": "scene_id",
    "标题": "title",
    "场景信息": "scene_info",
    "角色": "characters",
    "人物": "characters",
    "场景目的": "scene_purpose",
    "核心冲突": "core_conflict",
    "内容块": "content_blocks",
    "内容": "content_blocks",
    "内容块编号": "content_block_id",
    "类型": "type",
    "文本": "text",
    "说话人": "speaker",
    "表演指示": "parenthetical",
    "来源段落编号": "source_paragraph_ids",
    "来源证据编号": "source_evidence_ids",
}


def _translate_chinese_keys(data: dict) -> dict:
    """Map Chinese JSON keys to English internal keys. Pass through unknown keys unmodified."""
    result: dict = {}
    for key, value in data.items():
        mapped = CHINESE_KEY_MAP.get(key, key)
        if isinstance(value, dict):
            result[mapped] = _translate_chinese_keys(value)
        elif isinstance(value, list):
            result[mapped] = [
                _translate_chinese_keys(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[mapped] = value
    return result


def _validate_script_scene_payload(payload: dict, scene: ScenePlanScene, paragraph_ids: set[str]) -> dict:
    payload = _translate_chinese_keys(payload)
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
        parenthetical = block.get("parenthetical")
        source_paragraph_ids = block.get("source_paragraph_ids")
        source_evidence_ids = block.get("source_evidence_ids", [])
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
        if not isinstance(source_paragraph_ids, list):
            raise RuntimeError("script_generation source_paragraph_ids must be a list")
        if not source_paragraph_ids:
            raise RuntimeError(f"script_generation {content_block_id} source_paragraph_ids must be non-empty")
        if any(not isinstance(paragraph_id, str) or not paragraph_id.strip() for paragraph_id in source_paragraph_ids):
            raise RuntimeError("script_generation source_paragraph_ids must contain non-empty strings")
        normalized_source_paragraph_ids = normalize_paragraph_ids(
            [paragraph_id.strip() for paragraph_id in source_paragraph_ids],
            paragraph_ids,
        )
        unknown_paragraphs = set(normalized_source_paragraph_ids) - paragraph_ids
        if unknown_paragraphs:
            raise RuntimeError(f"script_generation references unknown paragraphs: {sorted(unknown_paragraphs)}")
        outside_scene = set(normalized_source_paragraph_ids) - set(scene.source_paragraph_ids or [])
        if outside_scene:
            raise RuntimeError(f"script_generation references paragraphs outside scene plan: {sorted(outside_scene)}")
        if not isinstance(source_evidence_ids, list):
            raise RuntimeError("script_generation source_evidence_ids must be a list")
        seen_block_ids.add(content_block_id)
        validated_blocks.append(
            {
                "content_block_id": content_block_id.strip(),
                "order": expected_order,
                "type": block_type,
                "text": text.strip(),
                "speaker": speaker.strip() if isinstance(speaker, str) else None,
                "source_evidence_ids": [],
                "source_paragraph_ids": normalized_source_paragraph_ids,
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
                        "parenthetical": block.parenthetical,
                        "source_evidence_ids": block.source_evidence_ids,
                        "source_paragraph_ids": block.source_paragraph_ids,
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
                "parenthetical": block.parenthetical,
                "source_evidence_ids": block.source_evidence_ids,
                "source_paragraph_ids": block.source_paragraph_ids,
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
