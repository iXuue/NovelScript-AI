import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.models.repair import RepairAttempt
from app.models.scene_plan import ScenePlan, ScenePlanScene, ScenePlanValidation
from app.models.story import StoryBible
from app.models.style import StyleProfile
from app.services.artifact_service import mark_downstream_stale
from app.services.checkpoint_service import create_checkpoint
from app.services.context_budget_service import compact_lines, generate_with_context_log, rank_evidence_items, truncate_text
from app.services.llm_provider import LLMProvider
from app.services.project_service import update_project_stage, update_project_stage_in_db
from app.services.source_id_service import normalize_paragraph_ids
from app.services.store import STORE, now_utc, persistent_id
from app.services.style_service import lock_style_source


TEXT_FIELDS = [
    "scene_id",
    "title",
    "interior_exterior",
    "location",
    "time",
    "scene_function",
    "core_conflict",
    "adaptation_note",
]
LIST_FIELDS = [
    "source_chapter_ids",
    "source_evidence_ids",
    "source_paragraph_ids",
    "characters",
    "must_cover_plot",
    "must_keep_dialogue",
    "must_keep_visual_elements",
    "must_keep_foreshadowing",
]
MAX_REPAIR_ATTEMPTS = 2
CHAPTER_SCENE_TEXT_FIELDS = [
    "title",
    "interior_exterior",
    "location",
    "time",
    "scene_function",
    "core_conflict",
    "adaptation_note",
]
CHAPTER_SCENE_LIST_FIELDS = [
    "source_paragraph_ids",
    "characters",
    "must_cover_plot",
    "must_keep_dialogue",
    "must_keep_visual_elements",
    "must_keep_foreshadowing",
]


def generate_scene_plan_artifact(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None,
    run_id: str | None = None,
    feedback_plan: dict | None = None,
) -> dict:
    chapters = _confirmed_chapters(db, project_id)
    summaries = _chapter_summaries(db, project_id)
    style_profile = _style_profile(db, project_id)
    if not chapters:
        raise RuntimeError("scene_plan requires confirmed chapters")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to generate Scene Plan")

    summary_by_chapter = {summary.chapter_id: summary for summary in summaries}
    paragraphs_by_chapter = _paragraphs_by_chapter(db, project_id)
    current_scene_plan = _current_scene_plan_for_feedback(db, project_id) if feedback_plan is not None else None
    scenes: list[dict] = []
    model_names: list[str] = []
    previous_last_scene: dict | None = None
    for chapter in chapters:
        paragraphs = paragraphs_by_chapter.get(chapter.chapter_id, [])
        prompt_paragraphs = _paragraphs_for_scene_plan_feedback(chapter, paragraphs, current_scene_plan, feedback_plan)
        summary = summary_by_chapter.get(chapter.chapter_id)
        if summary is None:
            raise RuntimeError(f"scene_plan requires chapter summary for {chapter.chapter_id}")
        response = generate_with_context_log(
            llm_provider,
            task_type="scene_plan_chapter",
            prompt=_scene_plan_chapter_prompt(
                chapter,
                summary,
                prompt_paragraphs,
                style_profile,
                feedback_plan=feedback_plan,
                current_scene_plan=current_scene_plan,
                previous_last_scene=previous_last_scene,
            ),
            response_format="json",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="scene_plan",
            chunk_range={"chapter_id": chapter.chapter_id, "chapter_order": chapter.order},
            source_item_count=1 + len(paragraphs),
            included_item_count=1 + len(prompt_paragraphs),
        )
        model_names.append(response.model_name)
        chapter_scenes = _validate_chapter_scene_plan_payload(_load_json_object(response.text), chapter, paragraphs)
        scenes.extend(chapter_scenes)
        if chapter_scenes:
            previous_last_scene = chapter_scenes[-1]

    payload = _validate_scene_plan_payload(
        {"scenes": _renumber_scenes(scenes)},
        chapter_ids={chapter.chapter_id for chapter in chapters},
        paragraph_ids={paragraph.paragraph_id for paragraphs in paragraphs_by_chapter.values() for paragraph in paragraphs},
    )
    scene_plan = _replace_scene_plan(db, project_id, payload["scenes"], ",".join(sorted(set(model_names))) or "unknown")
    _validate_and_store_scene_plan(db, scene_plan, chapters, paragraphs_by_chapter)
    return scene_plan_to_dict(scene_plan)


def get_current_scene_plan(db: Session | None, project_id: str) -> dict | None:
    if db is None:
        return STORE.scene_plans.get(project_id)
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.status == ArtifactStatus.current, ScenePlan.is_current.is_(True))
        .one_or_none()
    )
    if scene_plan is None:
        return None
    return scene_plan_to_dict(scene_plan)


def repair_current_scene_plan(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None,
    run_id: str | None = None,
) -> dict:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.status == ArtifactStatus.current, ScenePlan.is_current.is_(True))
        .one_or_none()
    )
    if scene_plan is None:
        raise KeyError("scene_plan_missing")
    validation = _latest_validation(scene_plan)
    if validation is None or validation.passed:
        raise PermissionError("scene_plan_repair_not_required")
    if _repair_attempt_count(db, project_id=project_id, artifact_type="scene_plan", artifact_id=None, scene_id=None) >= MAX_REPAIR_ATTEMPTS:
        raise PermissionError("repair_attempts_exceeded")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to repair Scene Plan")

    previous_scene_plan_id = scene_plan.scene_plan_id
    repaired_dict = generate_scene_plan_artifact(db, project_id, llm_provider, run_id=run_id)
    repaired = db.query(ScenePlan).filter(ScenePlan.scene_plan_id == repaired_dict["scene_plan_id"]).one()
    repaired_validation = _latest_validation(repaired)
    _record_repair_attempt(
        db,
        project_id=project_id,
        artifact_type="scene_plan",
        artifact_id=previous_scene_plan_id,
        result_artifact_id=repaired.scene_plan_id,
        scene_id=None,
        issues=validation.issues,
        status="success" if repaired_validation is not None and repaired_validation.passed else "failed",
        source=repaired.source,
    )
    STORE.scene_plans[project_id] = scene_plan_to_dict(repaired)
    return scene_plan_to_dict(repaired)


def confirm_current_scene_plan(db: Session, project_id: str, confirmation_source: str, message_id: str | None = None) -> dict:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.status == ArtifactStatus.current, ScenePlan.is_current.is_(True))
        .one_or_none()
    )
    if scene_plan is None:
        raise KeyError("scene_plan_missing")
    validation = _latest_validation(scene_plan)
    if validation is None or not validation.passed:
        raise PermissionError("scene_plan_validation_failed")
    scene_plan.confirmed = True
    scene_plan.updated_at = now_utc()
    db.commit()

    update_project_stage(project_id, ProjectStage.scene_plan_confirmed)
    update_project_stage_in_db(db, project_id, ProjectStage.scene_plan_confirmed)
    lock_style_source(project_id, db)
    checkpoint = create_checkpoint(project_id, "scene_plan_confirmed", db)
    cached = STORE.scene_plans.get(project_id)
    if cached is not None:
        cached["confirmed"] = True
    return {
        "project_id": project_id,
        "scene_plan_id": scene_plan.scene_plan_id,
        "confirmed": True,
        "style_locked": True,
        "checkpoint_id": checkpoint["checkpoint_id"],
    }


def scene_plan_to_dict(scene_plan: ScenePlan) -> dict:
    scenes = sorted(scene_plan.scenes, key=lambda scene: scene.order)
    validation = _latest_validation(scene_plan)
    return {
        "scene_plan_id": scene_plan.scene_plan_id,
        "status": scene_plan.status,
        "confirmed": scene_plan.confirmed,
        "validation": _validation_to_dict(validation) if validation is not None else None,
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "order": scene.order,
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
            }
            for scene in scenes
        ],
    }


def _replace_scene_plan(db: Session, project_id: str, scenes: list[dict], source: str) -> ScenePlan:
    mark_downstream_stale(db, f"scene_plan:{project_id}")
    previous_current = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True))
        .order_by(ScenePlan.version_number.desc())
        .first()
    )
    for current in db.query(ScenePlan).filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True)).all():
        current.is_current = False
        if current.status == ArtifactStatus.current:
            current.status = ArtifactStatus.historical
        current.stale_reason = "replaced_by_new_scene_plan"
        current.updated_at = now_utc()
    next_version_number = (
        db.query(ScenePlan.version_number)
        .filter(ScenePlan.project_id == project_id)
        .order_by(ScenePlan.version_number.desc())
        .first()
    )
    version_number = (next_version_number[0] if next_version_number else 0) + 1
    timestamp = now_utc()
    scene_plan = ScenePlan(
        scene_plan_id=persistent_id("sp"),
        project_id=project_id,
        version_number=version_number,
        is_current=True,
        parent_scene_plan_id=previous_current.scene_plan_id if previous_current is not None else None,
        stale_reason=None,
        status=ArtifactStatus.current,
        confirmed=False,
        source=source,
        created_at=timestamp,
        updated_at=timestamp,
    )
    scene_plan.scenes = [
        ScenePlanScene(
            scene_plan_id=scene_plan.scene_plan_id,
            project_id=project_id,
            scene_id=scene["scene_id"],
            order=scene["order"],
            title=scene["title"],
            source_chapter_ids=scene["source_chapter_ids"],
            source_evidence_ids=scene["source_evidence_ids"],
            source_paragraph_ids=scene["source_paragraph_ids"],
            interior_exterior=scene["interior_exterior"],
            location=scene["location"],
            time=scene["time"],
            characters=scene["characters"],
            must_cover_plot=scene["must_cover_plot"],
            must_keep_dialogue=scene["must_keep_dialogue"],
            must_keep_visual_elements=scene["must_keep_visual_elements"],
            must_keep_foreshadowing=scene["must_keep_foreshadowing"],
            scene_function=scene["scene_function"],
            core_conflict=scene["core_conflict"],
            adaptation_note=scene["adaptation_note"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        for scene in scenes
    ]
    db.add(scene_plan)
    db.commit()
    db.refresh(scene_plan)
    return scene_plan


def _validate_and_store_scene_plan(
    db: Session,
    scene_plan: ScenePlan,
    chapters: list[Chapter],
    paragraphs_by_chapter: dict[str, list[Paragraph]],
) -> ScenePlanValidation:
    payload = _deterministic_scene_plan_validation(scene_plan, chapters, paragraphs_by_chapter)
    timestamp = now_utc()
    validation = ScenePlanValidation(
        scene_plan_id=scene_plan.scene_plan_id,
        project_id=scene_plan.project_id,
        passed=payload["passed"],
        issues=payload["issues"],
        suggestions=payload["suggestions"],
        coverage=payload["coverage"],
        source="deterministic",
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(validation)
    db.commit()
    db.refresh(scene_plan)
    return validation


def _previous_scene_excerpt(scene: dict) -> dict:
    return {
        "title": scene.get("title"),
        "location": scene.get("location"),
        "time": scene.get("time"),
        "characters": scene.get("characters"),
        "scene_function": scene.get("scene_function"),
        "core_conflict": scene.get("core_conflict"),
        "adaptation_note": scene.get("adaptation_note"),
        "source_chapter_ids": scene.get("source_chapter_ids"),
    }


def _scene_plan_chapter_prompt(
    chapter: Chapter,
    summary: ChapterSummary,
    paragraphs: list[Paragraph],
    style_profile: StyleProfile | None,
    feedback_plan: dict | None = None,
    current_scene_plan: dict | None = None,
    previous_last_scene: dict | None = None,
) -> str:
    style_text = (
        style_profile.profile_text
        if style_profile is not None
        else "Use a neutral, clear adaptation style. Keep scenes filmable, concise, and faithful to the source material."
    )
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
            f"{json.dumps(feedback_context, ensure_ascii=False)}\n\n"
            "current_scene_plan_excerpt:\n"
            f"{json.dumps(_scene_plan_chapter_excerpt(current_scene_plan, chapter.chapter_id), ensure_ascii=False)}"
        )
    prev_scene_text = ""
    if previous_last_scene is not None:
        prev_scene_text = (
            "\n\nprevious_chapter_last_scene:\n"
            f"{json.dumps(_previous_scene_excerpt(previous_last_scene), ensure_ascii=False)}\n\n"
            "This is the final scene from the immediately preceding chapter. "
            "If this scene represents an event that spans across chapter boundaries "
            "(such as an ongoing conversation, an unresolved action, or a cliffhanger), "
            "you may create one or more scenes that continue or resolve it. "
            "Otherwise, treat chapters independently and do not force a connection.\n"
        )
    return (
        "You are the Scene Plan Worker for one confirmed novel chapter.\n"
        "Create filmable scene-outline entries for this chapter only. Use only supplied chapter summary and paragraphs.\n"
        "Return only one JSON object. No Markdown. No explanation.\n"
        "JSON schema: {\"scenes\":[{\"title\":\"...\",\"source_paragraph_ids\":[\"CH001_P001\"],"
        "\"interior_exterior\":\"内景/外景/内外景\",\"location\":\"...\",\"time\":\"...\",\"characters\":[\"...\"],"
        "\"must_cover_plot\":[\"...\"],\"must_keep_dialogue\":[\"...\"],"
        "\"must_keep_visual_elements\":[\"...\"],\"must_keep_foreshadowing\":[\"...\"],"
        "\"scene_function\":\"...\",\"core_conflict\":\"...\",\"adaptation_note\":\"...\"}]}\n"
        "Rules:\n"
        "- Generate one or more scenes for this chapter.\n"
        "- source_paragraph_ids must reference paragraph IDs from this chapter only and must not be empty.\n"
        "- Do not invent major characters, locations, or plot facts beyond the supplied materials.\n"
        "- Use [] for optional list fields only when nothing relevant is present.\n"
        "- Make scene_function describe what the scene achieves structurally.\n"
        "- Make adaptation_note describe how to translate novel material into screen action.\n\n"
        f"chapter:\n{json.dumps({'chapter_id': chapter.chapter_id, 'order': chapter.order, 'title': chapter.title}, ensure_ascii=False)}\n\n"
        f"chapter_summary:\n{_one_summary_block(summary)}\n\n"
        f"paragraphs:\n{_paragraph_block(paragraphs)}\n\n"
        f"style_profile:\n{style_text}"
        f"{prev_scene_text}"
        f"{feedback_text}"
    )


def _validate_chapter_scene_plan_payload(payload: dict, chapter: Chapter, paragraphs: list[Paragraph]) -> list[dict]:
    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("scene_plan_chapter field scenes must be a non-empty list")
    paragraph_ids = {paragraph.paragraph_id for paragraph in paragraphs}
    validated_scenes = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise RuntimeError("scene_plan_chapter scenes must contain JSON objects")
        validated = {
            "source_chapter_ids": [chapter.chapter_id],
            "source_evidence_ids": [],
        }
        for field in CHAPTER_SCENE_TEXT_FIELDS:
            value = scene.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"scene_plan_chapter scene field {field} must be a non-empty string")
            validated[field] = value.strip()
        for field in CHAPTER_SCENE_LIST_FIELDS:
            value = scene.get(field)
            validated[field] = _normalize_scene_list_field(value, field, "scene_plan_chapter")
        if not validated["source_paragraph_ids"]:
            raise RuntimeError("scene_plan_chapter source_paragraph_ids must be non-empty")
        if any(not isinstance(paragraph_id, str) or not paragraph_id.strip() for paragraph_id in validated["source_paragraph_ids"]):
            raise RuntimeError("scene_plan_chapter source_paragraph_ids must contain non-empty strings")
        validated["source_paragraph_ids"] = normalize_paragraph_ids(
            [paragraph_id.strip() for paragraph_id in validated["source_paragraph_ids"]],
            paragraph_ids,
        )
        unknown_paragraphs = set(validated["source_paragraph_ids"]) - paragraph_ids
        if unknown_paragraphs:
            raise RuntimeError(f"scene_plan_chapter references unknown paragraphs: {sorted(unknown_paragraphs)}")
        validated_scenes.append(validated)
    return validated_scenes


def _renumber_scenes(scenes: list[dict]) -> list[dict]:
    numbered = []
    for index, scene in enumerate(scenes, start=1):
        numbered.append({**scene, "scene_id": f"S{index:03d}", "order": index})
    return numbered


def _deterministic_scene_plan_validation(
    scene_plan: ScenePlan,
    chapters: list[Chapter],
    paragraphs_by_chapter: dict[str, list[Paragraph]],
) -> dict:
    issues = []
    chapter_ids = {chapter.chapter_id for chapter in chapters}
    paragraph_ids = {paragraph.paragraph_id for paragraphs in paragraphs_by_chapter.values() for paragraph in paragraphs}
    covered_chapters = set()
    covered_paragraphs = set()
    scenes = sorted(scene_plan.scenes, key=lambda scene: scene.order)
    if not scenes:
        issues.append({"code": "empty_scene_plan", "message": "Scene Plan must contain at least one scene"})
    for expected_order, scene in enumerate(scenes, start=1):
        if scene.order != expected_order or scene.scene_id != f"S{expected_order:03d}":
            issues.append({"code": "invalid_order", "message": f"{scene.scene_id} order must be consecutive"})
        if not scene.source_chapter_ids:
            issues.append({"code": "missing_chapter_reference", "message": f"{scene.scene_id} must reference a chapter"})
        if not scene.source_paragraph_ids:
            issues.append({"code": "missing_paragraph_reference", "message": f"{scene.scene_id} must reference paragraphs"})
        unknown_chapters = set(scene.source_chapter_ids) - chapter_ids
        unknown_paragraphs = set(scene.source_paragraph_ids) - paragraph_ids
        if unknown_chapters:
            issues.append({"code": "unknown_chapter", "message": f"{scene.scene_id} references unknown chapters: {sorted(unknown_chapters)}"})
        if unknown_paragraphs:
            issues.append({"code": "unknown_paragraph", "message": f"{scene.scene_id} references unknown paragraphs: {sorted(unknown_paragraphs)}"})
        covered_chapters.update(scene.source_chapter_ids)
        covered_paragraphs.update(scene.source_paragraph_ids)
    missing_chapters = chapter_ids - covered_chapters
    if missing_chapters:
        issues.append({"code": "missing_chapter_coverage", "message": f"Missing confirmed chapters: {sorted(missing_chapters)}"})
    return {
        "passed": not issues,
        "issues": issues,
        "suggestions": [],
        "coverage": {
            "chapter_ids": sorted(covered_chapters & chapter_ids),
            "paragraph_ids": sorted(covered_paragraphs & paragraph_ids),
        },
    }


def _scene_plan_prompt(
    chapters: list[Chapter],
    summaries: list[ChapterSummary],
    evidence_items: list[EvidenceItem],
    story_bible: StoryBible,
    style_profile: StyleProfile | None,
) -> str:
    style_text = (
        style_profile.profile_text
        if style_profile is not None
        else "Use a neutral, clear adaptation style. Keep scenes filmable, concise, and faithful to the source material."
    )
    return (
        "You are the Scene Plan Worker for a novel-to-screenplay adaptation pipeline.\n"
        "Create a scene-level outline, not screenplay prose. Use only supplied source facts.\n"
        "Each scene must be filmable, ordered, and tied back to existing chapter_ids and evidence_ids.\n"
        "Return only one JSON object. No Markdown. No explanation.\n"
        "JSON schema: {\"scenes\":[{\"scene_id\":\"S001\",\"order\":1,\"title\":\"...\","
        "\"source_chapter_ids\":[\"CH001\"],\"source_evidence_ids\":[\"EV001\"],"
        "\"interior_exterior\":\"内景/外景/内外景\",\"location\":\"...\",\"time\":\"...\",\"characters\":[\"...\"],"
        "\"must_cover_plot\":[\"...\"],\"must_keep_dialogue\":[\"...\"],"
        "\"must_keep_visual_elements\":[\"...\"],\"must_keep_foreshadowing\":[\"...\"],"
        "\"scene_function\":\"...\",\"core_conflict\":\"...\",\"adaptation_note\":\"...\"}]}\n"
        "Rules:\n"
        "- scene_id must be S001, S002... in order.\n"
        "- source_chapter_ids must reference confirmed chapters below.\n"
        "- source_evidence_ids must reference evidence below; use an empty list only if no evidence is relevant.\n"
        "- interior_exterior must say whether the scene is 内景, 外景, or 内外景.\n"
        "- must_cover_plot lists plot beats that this scene must cover.\n"
        "- must_keep_dialogue lists source dialogue lines that must remain; use [] if no dialogue must remain.\n"
        "- must_keep_visual_elements lists visual source details that must remain on screen.\n"
        "- must_keep_foreshadowing lists foreshadowing/clues that must remain; use [] if none.\n"
        "- Do not invent new major characters, locations, or plot facts beyond the inputs.\n"
        "- Use story_bible.theme as a continuity constraint for scene_function, core_conflict, and adaptation_note; do not redefine or overwrite the established theme.\n"
        "- Make scene_function describe what the scene achieves structurally.\n"
        "- Make adaptation_note describe how to translate novel material into screen action.\n\n"
        f"confirmed_chapters:\n{_chapter_block(chapters)}\n\n"
        f"chapter_summaries:\n{_summary_block(summaries)}\n\n"
        f"evidence_index:\n{_evidence_block(evidence_items)}\n\n"
        f"story_bible:\n{_story_bible_block(story_bible)}\n\n"
        f"style_profile:\n{style_text}"
    )


def _scene_plan_validation_prompt(
    scene_plan: ScenePlan,
    chapters: list[Chapter],
    summaries: list[ChapterSummary],
    evidence_items: list[EvidenceItem],
    story_bible: StoryBible,
) -> str:
    return (
        "You are the Scene Plan Validator. Validate the generated scene plan before user confirmation.\n"
        "Return only one JSON object. No Markdown. No explanation.\n"
        "JSON schema: {\"passed\":true,\"issues\":[],\"suggestions\":[],"
        "\"coverage\":{\"chapter_ids\":[\"CH001\"],\"evidence_ids\":[\"EV001\"]}}\n"
        "Validation checklist:\n"
        "- All confirmed chapters are covered by at least one scene.\n"
        "- All referenced chapter_ids and evidence_ids exist.\n"
        "- Key chapter summary events, important evidence, required dialogue, visual elements, and foreshadowing are assigned to scenes.\n"
        "- Scene order is coherent and no major unsupported facts are invented.\n"
        "- Each scene has clear interior/exterior, location, time, characters, purpose, conflict, and adaptation note.\n\n"
        f"confirmed_chapters:\n{_chapter_block(chapters)}\n\n"
        f"chapter_summaries:\n{_summary_block(summaries)}\n\n"
        f"evidence_index:\n{_evidence_block(evidence_items)}\n\n"
        f"story_bible:\n{_story_bible_block(story_bible)}\n\n"
        f"scene_plan:\n{json.dumps(scene_plan_to_dict_without_validation(scene_plan), ensure_ascii=False)}"
    )


def _scene_plan_repair_prompt(
    scene_plan: ScenePlan,
    validation: ScenePlanValidation,
    chapters: list[Chapter],
    summaries: list[ChapterSummary],
    evidence_items: list[EvidenceItem],
    story_bible: StoryBible,
) -> str:
    return (
        "You are the Scene Plan Repair Worker. Repair the current scene plan according to validation issues.\n"
        "Return the full repaired Scene Plan as one JSON object. No Markdown. No explanation.\n"
        "Use the same schema as Scene Plan generation: {\"scenes\":[...]}.\n"
        "Rules:\n"
        "- Preserve valid scene plan material when possible.\n"
        "- Fix only issues identified by validation unless required for consistency.\n"
        "- Reuse existing chapter_ids and evidence_ids only.\n"
        "- Do not invent unsupported facts.\n\n"
        f"validation_issues:\n{json.dumps(validation.issues, ensure_ascii=False)}\n\n"
        f"validation_suggestions:\n{json.dumps(validation.suggestions, ensure_ascii=False)}\n\n"
        f"current_scene_plan:\n{json.dumps(scene_plan_to_dict_without_validation(scene_plan), ensure_ascii=False)}\n\n"
        f"confirmed_chapters:\n{_chapter_block(chapters)}\n\n"
        f"chapter_summaries:\n{_summary_block(summaries)}\n\n"
        f"evidence_index:\n{_evidence_block(evidence_items)}\n\n"
        f"story_bible:\n{_story_bible_block(story_bible)}"
    )


def scene_plan_to_dict_without_validation(scene_plan: ScenePlan) -> dict:
    data = scene_plan_to_dict(scene_plan)
    data.pop("validation", None)
    return data


def _current_scene_plan_for_feedback(db: Session, project_id: str) -> dict | None:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.is_current.is_(True))
        .order_by(ScenePlan.version_number.desc())
        .first()
    )
    return scene_plan_to_dict_without_validation(scene_plan) if scene_plan is not None else None


def _paragraphs_for_scene_plan_feedback(
    chapter: Chapter,
    paragraphs: list[Paragraph],
    current_scene_plan: dict | None,
    feedback_plan: dict | None,
) -> list[Paragraph]:
    if feedback_plan is None:
        return paragraphs
    requested_ids = set()
    for request in feedback_plan.get("source_requests") or []:
        if isinstance(request, dict):
            requested_ids.update(str(paragraph_id) for paragraph_id in request.get("paragraph_ids") or [])
    chapter_paragraph_ids = {paragraph.paragraph_id for paragraph in paragraphs}
    selected_ids = requested_ids & chapter_paragraph_ids
    if not selected_ids and current_scene_plan is not None:
        for scene in current_scene_plan.get("scenes") or []:
            if chapter.chapter_id in (scene.get("source_chapter_ids") or []):
                selected_ids.update(paragraph_id for paragraph_id in scene.get("source_paragraph_ids") or [] if paragraph_id in chapter_paragraph_ids)
    if not selected_ids:
        return paragraphs
    selected = [paragraph for paragraph in paragraphs if paragraph.paragraph_id in selected_ids]
    return selected or paragraphs


def _scene_plan_chapter_excerpt(current_scene_plan: dict | None, chapter_id: str) -> dict:
    if current_scene_plan is None:
        return {"scenes": []}
    return {
        "scene_plan_id": current_scene_plan.get("scene_plan_id"),
        "scenes": [
            {
                "scene_id": scene.get("scene_id"),
                "title": scene.get("title"),
                "source_chapter_ids": scene.get("source_chapter_ids"),
                "source_paragraph_ids": scene.get("source_paragraph_ids"),
                "location": scene.get("location"),
                "time": scene.get("time"),
                "characters": scene.get("characters"),
                "scene_function": scene.get("scene_function"),
                "core_conflict": scene.get("core_conflict"),
            }
            for scene in current_scene_plan.get("scenes") or []
            if chapter_id in (scene.get("source_chapter_ids") or [])
        ],
    }


def _chapter_block(chapters: list[Chapter]) -> str:
    return "\n".join(
        json.dumps({"chapter_id": chapter.chapter_id, "order": chapter.order, "title": chapter.title}, ensure_ascii=False)
        for chapter in chapters
    )


def _one_summary_block(summary: ChapterSummary) -> str:
    return json.dumps(
        {
            "chapter_id": summary.chapter_id,
            "title": summary.title,
            "summary": truncate_text(summary.summary, 1200),
            "key_events": summary.key_events,
            "characters": summary.characters,
            "locations": summary.locations,
            "conflicts": summary.conflicts,
            "foreshadowing": summary.foreshadowing,
            "adaptation_suggestions": summary.adaptation_suggestions,
        },
        ensure_ascii=False,
    )


def _summary_block(summaries: list[ChapterSummary]) -> str:
    return compact_lines(
        (
            _one_summary_block(summary)
            for summary in summaries
        ),
        8000,
    )


def _paragraph_block(paragraphs: list[Paragraph]) -> str:
    return compact_lines(
        (
            json.dumps(
                {
                    "paragraph_id": paragraph.paragraph_id,
                    "text": truncate_text(paragraph.text, 800, ""),
                },
                ensure_ascii=False,
            )
            for paragraph in paragraphs
        ),
        8000,
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
                "evidence_type": evidence.evidence_type,
                "explanation": evidence.explanation,
                "related_characters": evidence.related_characters,
                "related_locations": evidence.related_locations,
                "related_plot_points": evidence.related_plot_points,
                "importance": evidence.importance,
                "must_keep": evidence.must_keep,
            },
            ensure_ascii=False,
        )
        for evidence in ranked
        ),
        8000,
    )


def _story_bible_block(story_bible: StoryBible) -> str:
    return json.dumps(
        {
            "title": story_bible.title,
            "story_type": story_bible.story_type,
            "tone": story_bible.tone,
            "logline": truncate_text(story_bible.logline, 800),
            "theme": truncate_text(story_bible.theme, 800),
            "main_characters": story_bible.main_characters,
            "relationships": story_bible.relationships,
            "locations": story_bible.locations,
            "timeline": story_bible.timeline,
            "central_conflict": truncate_text(story_bible.central_conflict, 800),
            "foreshadowing": story_bible.foreshadowing,
        },
        ensure_ascii=False,
    )


def _confirmed_chapters(db: Session, project_id: str) -> list[Chapter]:
    return (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id, Chapter.status == "confirmed")
        .order_by(Chapter.order)
        .all()
    )


def _chapter_summaries(db: Session, project_id: str) -> list[ChapterSummary]:
    return (
        db.query(ChapterSummary)
        .filter(ChapterSummary.project_id == project_id)
        .order_by(ChapterSummary.chapter_id)
        .all()
    )


def _paragraphs_by_chapter(db: Session, project_id: str) -> dict[str, list[Paragraph]]:
    paragraphs = (
        db.query(Paragraph)
        .filter(Paragraph.project_id == project_id)
        .order_by(Paragraph.chapter_id, Paragraph.order)
        .all()
    )
    by_chapter: dict[str, list[Paragraph]] = {}
    for paragraph in paragraphs:
        by_chapter.setdefault(paragraph.chapter_id, []).append(paragraph)
    return by_chapter


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
        raise RuntimeError("scene_plan provider returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("scene_plan provider response must be a JSON object")
    return payload


def _validate_scene_plan_payload(payload: dict, chapter_ids: set[str], paragraph_ids: set[str]) -> dict:
    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("scene_plan field scenes must be a non-empty list")
    seen_scene_ids: set[str] = set()
    validated_scenes = []
    for expected_order, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise RuntimeError("scene_plan scenes must contain JSON objects")
        validated = {"order": _validated_order(scene, expected_order)}
        for field in TEXT_FIELDS:
            value = scene.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(f"scene_plan scene field {field} must be a non-empty string")
            validated[field] = value.strip()
        for field in LIST_FIELDS:
            value = scene.get(field)
            validated[field] = _normalize_scene_list_field(value, field, "scene_plan")
        if validated["scene_id"] in seen_scene_ids:
            raise RuntimeError("scene_plan scene_id must be unique")
        if validated["scene_id"] != f"S{expected_order:03d}":
            raise RuntimeError("scene_plan scene_id must match scene order")
        if any(not isinstance(paragraph_id, str) or not paragraph_id.strip() for paragraph_id in validated["source_paragraph_ids"]):
            raise RuntimeError("scene_plan scene field source_paragraph_ids must contain non-empty strings")
        validated["source_paragraph_ids"] = normalize_paragraph_ids(
            [paragraph_id.strip() for paragraph_id in validated["source_paragraph_ids"]],
            paragraph_ids,
        )
        unknown_chapters = set(validated["source_chapter_ids"]) - chapter_ids
        unknown_paragraphs = set(validated["source_paragraph_ids"]) - paragraph_ids
        if unknown_chapters:
            raise RuntimeError(f"scene_plan references unknown chapters: {sorted(unknown_chapters)}")
        if unknown_paragraphs:
            raise RuntimeError(f"scene_plan references unknown paragraphs: {sorted(unknown_paragraphs)}")
        if not validated["source_paragraph_ids"]:
            raise RuntimeError("scene_plan scene field source_paragraph_ids must be non-empty")
        seen_scene_ids.add(validated["scene_id"])
        validated_scenes.append(validated)
    return {"scenes": validated_scenes}


def _validated_order(scene: dict, expected_order: int) -> int:
    order = scene.get("order")
    if not isinstance(order, int) or order != expected_order:
        raise RuntimeError("scene_plan order must be consecutive starting at 1")
    return order


def _normalize_scene_list_field(value: object, field: str, context: str) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    raise RuntimeError(f"{context} scene field {field} must be a list")


def _validate_scene_plan_validation_payload(payload: dict) -> dict:
    passed = payload.get("passed")
    issues = payload.get("issues")
    suggestions = payload.get("suggestions")
    coverage = payload.get("coverage")
    if not isinstance(passed, bool):
        raise RuntimeError("scene_plan_validation field passed must be a boolean")
    if not isinstance(issues, list):
        raise RuntimeError("scene_plan_validation field issues must be a list")
    if not isinstance(suggestions, list):
        raise RuntimeError("scene_plan_validation field suggestions must be a list")
    if not isinstance(coverage, dict):
        raise RuntimeError("scene_plan_validation field coverage must be an object")
    return {"passed": passed, "issues": issues, "suggestions": suggestions, "coverage": coverage}


def _latest_validation(scene_plan: ScenePlan) -> ScenePlanValidation | None:
    validations = sorted(scene_plan.validations, key=lambda item: item.created_at, reverse=True)
    return validations[0] if validations else None


def _validation_to_dict(validation: ScenePlanValidation) -> dict:
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
    artifact_id: str | None,
    scene_id: str | None,
) -> int:
    query = db.query(RepairAttempt).filter(
        RepairAttempt.project_id == project_id,
        RepairAttempt.artifact_type == artifact_type,
        RepairAttempt.scene_id == scene_id,
    )
    if artifact_id is not None:
        query = query.filter(RepairAttempt.artifact_id == artifact_id)
    return query.count()
