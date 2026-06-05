from dataclasses import dataclass, field

from app.domain.artifacts import ArtifactStatus, ProjectStage
from app.models.chapter import Chapter
from app.services.analysis_worker_service import run_initial_text_analysis
from app.services.chapter_service import Paragraph
from app.services.export_service import to_yaml_preview
from app.services.llm_provider import LLMProvider
from app.services.project_service import update_project_stage
from app.services.run_service import create_project_run
from app.services.scene_plan_service import confirm_current_scene_plan, generate_scene_plan_artifact
from app.services.script_service import generate_script_from_confirmed_scene_plan
from app.services.store import STORE, now_utc
from app.services.story_bible_service import generate_story_bible
from app.services.style_profile_service import generate_style_profile


@dataclass
class OrchestrationPlan:
    parallel_groups: list[list[str]] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)


def build_initial_generation_plan() -> OrchestrationPlan:
    return OrchestrationPlan(
        parallel_groups=[["chapter_summary", "evidence_extraction", "style_profile"]],
        dependencies={
            "story_bible": ["chapter_summary", "evidence_extraction"],
            "scene_plan": ["story_bible", "style_profile"],
        },
    )


def generate_scene_plan(project_id: str, db=None, llm_provider: LLMProvider | None = None) -> dict:
    run = create_project_run(
        project_id,
        trigger_type="initial_analysis_scene_plan",
        stage="scene_plan",
        steps=[
            "chapter_summary",
            "evidence_extraction",
            "story_bible",
            "style_profile",
            "scene_plan",
        ],
    )
    if db is not None:
        run_initial_text_analysis(db, project_id, llm_provider)
        generate_story_bible(db, project_id, llm_provider)
        generate_style_profile(db, project_id, llm_provider)
        scene_plan = generate_scene_plan_artifact(db, project_id, llm_provider)
        STORE.scene_plans[project_id] = scene_plan
        update_project_stage(project_id, ProjectStage.scene_plan_draft)
        return {"run_id": run["run_id"], "scene_plan_id": scene_plan["scene_plan_id"], "status": "running"}
    scenes = []
    chapters = _confirmed_chapter_drafts(db, project_id) if db is not None else STORE.chapters_pending.get(project_id, [])
    for index, chapter in enumerate(chapters or [{"chapter_id": "CH001", "title": "未命名场景"}], start=1):
        scenes.append(
            {
                "scene_id": f"S{index:03d}",
                "order": index,
                "title": chapter["title"],
                "source_chapter_ids": [chapter["chapter_id"]],
                "source_evidence_ids": [f"EV{index:03d}"],
                "location": "待定地点",
                "time": "待定时间",
                "characters": [],
                "scene_function": "承接原文关键情节",
                "core_conflict": "角色目标与阻力尚待细化",
                "adaptation_note": "骨架阶段由确定性 Worker 生成",
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
        )
        result = generate_script_from_confirmed_scene_plan(db, project_id, llm_provider)
        result["run_id"] = run["run_id"]
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
    for scene_index, scene in enumerate(scene_plan["scenes"], start=1):
        paragraph = paragraphs[min(scene_index - 1, len(paragraphs) - 1)] if paragraphs else None
        block_id = f"CB{scene_index:03d}"
        evidence_id = f"EV{scene_index:03d}"
        text = paragraph.text if paragraph else "骨架剧本内容待生成。"
        block = {
            "content_block_id": block_id,
            "type": "action",
            "text": text,
            "speaker": None,
            "source_evidence_ids": [evidence_id],
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
                "display_label": f"{scene['scene_id']} 动作 1",
                "source_evidence_ids": [evidence_id],
            }
        )
        evidence_map[block_id] = {
            "content_block_id": block_id,
            "evidence": [
                {
                    "source_evidence_id": evidence_id,
                    "chapter_id": scene["source_chapter_ids"][0],
                    "paragraph_id": paragraph.paragraph_id if paragraph else f"{scene['source_chapter_ids'][0]}_P001",
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

