import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter
from app.models.scene_plan import ScenePlan, ScenePlanScene, ScenePlanValidation
from app.models.story import StoryBible
from app.models.style import StyleProfile
from app.services.checkpoint_service import create_checkpoint
from app.services.llm_provider import LLMProvider, LLMRequest
from app.services.project_service import update_project_stage, update_project_stage_in_db
from app.services.store import STORE, now_utc
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
    "characters",
    "must_cover_plot",
    "must_keep_dialogue",
    "must_keep_visual_elements",
    "must_keep_foreshadowing",
]


def generate_scene_plan_artifact(db: Session, project_id: str, llm_provider: LLMProvider | None) -> dict:
    chapters = _confirmed_chapters(db, project_id)
    summaries = _chapter_summaries(db, project_id)
    evidence_items = _evidence_items(db, project_id)
    story_bible = _story_bible(db, project_id)
    style_profile = _style_profile(db, project_id)
    if not chapters:
        raise RuntimeError("scene_plan requires confirmed chapters")
    if story_bible is None:
        raise RuntimeError("scene_plan requires story_bible")
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to generate Scene Plan")

    response = llm_provider.generate(
        LLMRequest(
            task_type="scene_plan",
            prompt=_scene_plan_prompt(chapters, summaries, evidence_items, story_bible, style_profile),
            response_format="json",
        )
    )
    payload = _validate_scene_plan_payload(
        _load_json_object(response.text),
        chapter_ids={chapter.chapter_id for chapter in chapters},
        evidence_ids={evidence.evidence_id for evidence in evidence_items},
    )
    scene_plan = _replace_scene_plan(db, project_id, payload["scenes"], response.model_name)
    _validate_and_store_scene_plan(db, scene_plan, chapters, summaries, evidence_items, story_bible, llm_provider)
    return scene_plan_to_dict(scene_plan)


def get_current_scene_plan(db: Session, project_id: str) -> dict | None:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.status == ArtifactStatus.current)
        .one_or_none()
    )
    if scene_plan is None:
        return None
    return scene_plan_to_dict(scene_plan)


def confirm_current_scene_plan(db: Session, project_id: str, confirmation_source: str, message_id: str | None = None) -> dict:
    scene_plan = (
        db.query(ScenePlan)
        .filter(ScenePlan.project_id == project_id, ScenePlan.status == ArtifactStatus.current)
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
    lock_style_source(project_id)
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
    db.execute(delete(ScenePlan).where(ScenePlan.project_id == project_id))
    timestamp = now_utc()
    scene_plan = ScenePlan(
        scene_plan_id=STORE.next_id("sp"),
        project_id=project_id,
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
    summaries: list[ChapterSummary],
    evidence_items: list[EvidenceItem],
    story_bible: StoryBible,
    llm_provider: LLMProvider,
) -> ScenePlanValidation:
    response = llm_provider.generate(
        LLMRequest(
            task_type="scene_plan_validation",
            prompt=_scene_plan_validation_prompt(scene_plan, chapters, summaries, evidence_items, story_bible),
            response_format="json",
        )
    )
    payload = _validate_scene_plan_validation_payload(_load_json_object(response.text))
    timestamp = now_utc()
    validation = ScenePlanValidation(
        scene_plan_id=scene_plan.scene_plan_id,
        project_id=scene_plan.project_id,
        passed=payload["passed"],
        issues=payload["issues"],
        suggestions=payload["suggestions"],
        coverage=payload["coverage"],
        source=response.model_name,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(validation)
    db.commit()
    db.refresh(scene_plan)
    return validation


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


def scene_plan_to_dict_without_validation(scene_plan: ScenePlan) -> dict:
    data = scene_plan_to_dict(scene_plan)
    data.pop("validation", None)
    return data


def _chapter_block(chapters: list[Chapter]) -> str:
    return "\n".join(
        json.dumps({"chapter_id": chapter.chapter_id, "order": chapter.order, "title": chapter.title}, ensure_ascii=False)
        for chapter in chapters
    )


def _summary_block(summaries: list[ChapterSummary]) -> str:
    return "\n".join(
        json.dumps(
            {
                "chapter_id": summary.chapter_id,
                "title": summary.title,
                "summary": summary.summary,
                "key_events": summary.key_events,
                "characters": summary.characters,
                "locations": summary.locations,
                "conflicts": summary.conflicts,
                "foreshadowing": summary.foreshadowing,
                "adaptation_suggestions": summary.adaptation_suggestions,
            },
            ensure_ascii=False,
        )
        for summary in summaries
    )


def _evidence_block(evidence_items: list[EvidenceItem]) -> str:
    return "\n".join(
        json.dumps(
            {
                "evidence_id": evidence.evidence_id,
                "chapter_id": evidence.chapter_id,
                "paragraph_id": evidence.paragraph_id,
                "quote": evidence.quote,
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
        for evidence in evidence_items
    )


def _story_bible_block(story_bible: StoryBible) -> str:
    return json.dumps(
        {
            "title": story_bible.title,
            "story_type": story_bible.story_type,
            "tone": story_bible.tone,
            "logline": story_bible.logline,
            "theme": story_bible.theme,
            "main_characters": story_bible.main_characters,
            "relationships": story_bible.relationships,
            "locations": story_bible.locations,
            "timeline": story_bible.timeline,
            "central_conflict": story_bible.central_conflict,
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


def _validate_scene_plan_payload(payload: dict, chapter_ids: set[str], evidence_ids: set[str]) -> dict:
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
            if not isinstance(value, list):
                raise RuntimeError(f"scene_plan scene field {field} must be a list")
            validated[field] = value
        if validated["scene_id"] in seen_scene_ids:
            raise RuntimeError("scene_plan scene_id must be unique")
        if validated["scene_id"] != f"S{expected_order:03d}":
            raise RuntimeError("scene_plan scene_id must match scene order")
        unknown_chapters = set(validated["source_chapter_ids"]) - chapter_ids
        unknown_evidence = set(validated["source_evidence_ids"]) - evidence_ids
        if unknown_chapters:
            raise RuntimeError(f"scene_plan references unknown chapters: {sorted(unknown_chapters)}")
        if unknown_evidence:
            raise RuntimeError(f"scene_plan references unknown evidence: {sorted(unknown_evidence)}")
        seen_scene_ids.add(validated["scene_id"])
        validated_scenes.append(validated)
    return {"scenes": validated_scenes}


def _validated_order(scene: dict, expected_order: int) -> int:
    order = scene.get("order")
    if not isinstance(order, int) or order != expected_order:
        raise RuntimeError("scene_plan order must be consecutive starting at 1")
    return order


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
