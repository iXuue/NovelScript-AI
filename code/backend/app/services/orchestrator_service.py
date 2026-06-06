from dataclasses import dataclass, field

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.chapter import Chapter
from app.services.analysis_worker_service import generate_chapter_summaries
from app.services.chapter_service import Paragraph
from app.services.export_service import to_yaml_preview
from app.services.local_snapshot_service import mirror_project_snapshot
from app.services.llm_provider import LLMProvider
from app.services.project_service import update_project_stage
from app.services.run_service import create_project_run, update_run_status, update_run_step
from app.services.scene_plan_service import confirm_current_scene_plan, generate_scene_plan_artifact
from app.services.script_service import generate_script_from_confirmed_scene_plan
from app.services.store import STORE, now_utc
from app.services.style_profile_service import generate_style_profile


@dataclass
class OrchestrationPlan:
    parallel_groups: list[list[str]] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)


def build_initial_generation_plan() -> OrchestrationPlan:
    return OrchestrationPlan(
        parallel_groups=[["chapter_summary", "style_profile"]],
        dependencies={"scene_plan": ["chapter_summary", "style_profile"]},
    )


def generate_scene_plan(project_id: str, db=None, llm_provider: LLMProvider | None = None) -> dict:
    run = create_project_run(
        project_id,
        trigger_type="initial_analysis_scene_plan",
        stage="scene_plan",
        steps=["chapter_summary", "style_profile", "scene_plan"],
        db=db,
    )
    if db is not None:
        run_id = run["run_id"]
        current_step = "chapter_summary"
        try:
            update_run_status(run_id, "running", db=db)
            print(f"[{project_id}] [START] Scene Plan generation")

            update_run_step(project_id, run_id, current_step, "running", db=db)
            generate_chapter_summaries(db, project_id, llm_provider, run_id=run_id)
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, current_step, "succeeded", "Chapter summaries completed", db=db)

            current_step = "style_profile"
            update_run_step(project_id, run_id, current_step, "running", db=db)
            generate_style_profile(db, project_id, llm_provider, run_id=run_id)
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, current_step, "succeeded", "Style Profile completed", db=db)

            current_step = "scene_plan"
            update_run_step(project_id, run_id, current_step, "running", db=db)
            scene_plan = generate_scene_plan_artifact(db, project_id, llm_provider, run_id=run_id)
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, current_step, "succeeded", "Scene Plan completed", db=db)

            STORE.scene_plans[project_id] = scene_plan
            update_project_stage(project_id, ProjectStage.scene_plan_draft)
            update_run_status(run_id, "succeeded", db=db)
            return {"run_id": run_id, "scene_plan_id": scene_plan["scene_plan_id"], "status": "running"}
        except Exception as exc:
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, current_step, "failed", str(exc), db=db)
            update_run_status(run_id, "failed", str(exc), db=db)
            raise

    scenes = []
    chapters = _confirmed_chapter_drafts(db, project_id) if db is not None else STORE.chapters_pending.get(project_id, [])
    for index, chapter in enumerate(chapters or [{"chapter_id": "CH001", "title": "Untitled Scene"}], start=1):
        paragraph_id = f"{chapter['chapter_id']}_P001"
        scenes.append(
            {
                "scene_id": f"S{index:03d}",
                "order": index,
                "title": chapter["title"],
                "source_chapter_ids": [chapter["chapter_id"]],
                "source_evidence_ids": [],
                "source_paragraph_ids": [paragraph_id],
                "location": "TBD",
                "time": "TBD",
                "characters": [],
                "scene_function": "Carry the key plot beats from the source chapter.",
                "core_conflict": "Character objective and obstacle are pending generation.",
                "adaptation_note": "Fallback scaffold generated without database persistence.",
            }
        )
    scene_plan_id = STORE.next_id("sp")
    STORE.scene_plans[project_id] = {
        "scene_plan_id": scene_plan_id,
        "status": ArtifactStatus.current,
        "confirmed": False,
        "scenes": scenes,
    }
    update_project_stage(project_id, ProjectStage.scene_plan_draft)
    return {"run_id": run["run_id"], "scene_plan_id": scene_plan_id, "status": "running"}


def _confirmed_chapter_drafts(db, project_id: str) -> list[dict]:
    return [
        {"chapter_id": chapter.chapter_id, "title": chapter.title}
        for chapter in (
            db.query(Chapter)
            .filter(Chapter.project_id == project_id, Chapter.status == "confirmed")
            .order_by(Chapter.order)
            .all()
        )
    ]


def confirm_scene_plan(project_id: str, confirmation_source: str, message_id: str | None = None, db=None) -> dict:
    if db is not None:
        return confirm_current_scene_plan(db, project_id, confirmation_source, message_id)
    scene_plan = STORE.scene_plans.get(project_id)
    if scene_plan is None:
        raise KeyError("scene_plan_missing")
    scene_plan["confirmed"] = True
    update_project_stage(project_id, ProjectStage.scene_plan_confirmed)
    STORE.style_locked.add(project_id)
    checkpoint_id = STORE.next_id("chk")
    return {
        "project_id": project_id,
        "scene_plan_id": scene_plan["scene_plan_id"],
        "confirmed": True,
        "style_locked": True,
        "checkpoint_id": checkpoint_id,
    }


def generate_script(project_id: str, db=None, llm_provider: LLMProvider | None = None) -> dict:
    if db is not None:
        run = create_project_run(
            project_id,
            trigger_type="script_generation",
            stage="script_generating",
            steps=["script_generation", "validation"],
            db=db,
        )
        run_id = run["run_id"]
        current_step = "script_generation"
        try:
            update_run_status(run_id, "running", db=db)
            update_run_step(project_id, run_id, current_step, "running", db=db)
            print(f"[{project_id}] [START] Script generation")
            result = generate_script_from_confirmed_scene_plan(db, project_id, llm_provider, run_id=run_id)
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, current_step, "succeeded", "Script generation completed", db=db)
            current_step = "validation"
            update_run_step(project_id, run_id, current_step, "succeeded", "Deterministic validation completed", db=db)
            update_run_status(run_id, "succeeded", db=db)
        except Exception as exc:
            mirror_project_snapshot(db, project_id)
            update_run_step(project_id, run_id, current_step, "failed", str(exc), db=db)
            update_run_status(run_id, "failed", str(exc), db=db)
            raise
        result["run_id"] = run_id
        return result

    scene_plan = STORE.scene_plans.get(project_id)
    if not scene_plan or not scene_plan.get("confirmed"):
        raise PermissionError("scene_plan_not_confirmed")
    run = create_project_run(
        project_id,
        trigger_type="script_generation",
        stage="script_generating",
        steps=["script_generation", "validation"],
    )
    content_blocks = []
    scenes = []
    evidence_map: dict[str, dict] = {}
    paragraphs: list[Paragraph] = [p for chapter in STORE.chapter_paragraphs.get(project_id, []) for p in chapter["paragraphs"]]
    paragraph_by_id = {paragraph.paragraph_id: paragraph for paragraph in paragraphs}
    for scene_index, scene in enumerate(scene_plan["scenes"], start=1):
        source_paragraph_ids = scene.get("source_paragraph_ids") or []
        paragraph = paragraph_by_id.get(source_paragraph_ids[0]) if source_paragraph_ids else None
        if paragraph is None and paragraphs:
            paragraph = paragraphs[min(scene_index - 1, len(paragraphs) - 1)]
            source_paragraph_ids = [paragraph.paragraph_id]
        block_id = f"CB{scene_index:03d}"
        text = paragraph.text if paragraph else "Fallback script content pending generation."
        block = {
            "content_block_id": block_id,
            "type": "action",
            "text": text,
            "speaker": None,
            "source_evidence_ids": [],
            "source_paragraph_ids": source_paragraph_ids,
        }
        scenes.append(
            {
                "scene_id": scene["scene_id"],
                "title": scene["title"],
                "source_chapter_ids": scene["source_chapter_ids"],
                "content_blocks": [block],
            }
        )
        content_blocks.append(
            {
                "content_block_id": block_id,
                "scene_id": scene["scene_id"],
                "block_type": "action",
                "display_label": f"{scene['scene_id']} Action 1",
                "source_evidence_ids": [],
                "source_paragraph_ids": source_paragraph_ids,
            }
        )
        fallback_paragraph_id = source_paragraph_ids[0] if source_paragraph_ids else f"{scene['source_chapter_ids'][0]}_P001"
        paragraph_id = paragraph.paragraph_id if paragraph else fallback_paragraph_id
        evidence_map[block_id] = {
            "content_block_id": block_id,
            "evidence": [
                {
                    "source_paragraph_id": paragraph_id,
                    "source_evidence_id": None,
                    "chapter_id": scene["source_chapter_ids"][0],
                    "paragraph_id": paragraph_id,
                    "paragraph_ids": [paragraph_id],
                    "text": text,
                }
            ],
        }

    script_version_id = STORE.next_id("script_v")
    generated_at = now_utc()
    internal = {"title": STORE.projects[project_id]["name"], "characters": [], "scenes": scenes}
    STORE.scripts[project_id] = {
        "script_version_id": script_version_id,
        "status": ArtifactStatus.current,
        "generated_at": generated_at,
        "internal": internal,
    }
    STORE.script_ui[project_id] = {
        "script_version_id": script_version_id,
        "status": ArtifactStatus.current,
        "generated_at": generated_at,
        "content_blocks": content_blocks,
    }
    STORE.yaml_previews[project_id] = {
        "script_version_id": script_version_id,
        "status": ArtifactStatus.current,
        "yaml": to_yaml_preview(internal),
        "generated_at": generated_at,
    }
    STORE.evidence_by_content_block.update(evidence_map)
    update_project_stage(project_id, ProjectStage.script_ready)
    return {"run_id": run["run_id"], "status": "running", "stage": "script_generating"}
