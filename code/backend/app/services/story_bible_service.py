import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.story import StoryBible
from app.services.context_budget_service import compact_lines, generate_with_context_log, rank_evidence_items, truncate_text
from app.services.llm_provider import LLMProvider
from app.services.store import now_utc


TEXT_FIELDS = ["title", "story_type", "tone", "logline", "theme", "central_conflict"]
LIST_FIELDS = ["main_characters", "relationships", "locations", "timeline", "foreshadowing"]


def generate_story_bible(db: Session, project_id: str, llm_provider: LLMProvider | None) -> StoryBible | None:
    summaries = _chapter_summaries(db, project_id)
    evidence_items = _evidence_items(db, project_id)
    if not summaries or not evidence_items:
        return None
    if llm_provider is None:
        raise RuntimeError("LLM provider is required to generate Story Bible")

    response = generate_with_context_log(
        llm_provider,
        task_type="story_bible",
        prompt=_story_bible_prompt(summaries, evidence_items),
        response_format="json",
        db=db,
        project_id=project_id,
        step_type="story_bible",
        source_item_count=len(summaries) + len(evidence_items),
        included_item_count=len(summaries) + min(len(evidence_items), 80),
    )
    payload = _validate_story_bible_payload(_load_json_object(response.text))
    return _replace_story_bible(db, project_id, payload, response.model_name)


def _replace_story_bible(db: Session, project_id: str, payload: dict, source: str) -> StoryBible:
    db.execute(delete(StoryBible).where(StoryBible.project_id == project_id))
    timestamp = now_utc()
    story_bible = StoryBible(
        project_id=project_id,
        title=payload["title"],
        story_type=payload["story_type"],
        tone=payload["tone"],
        logline=payload["logline"],
        theme=payload["theme"],
        main_characters=payload["main_characters"],
        relationships=payload["relationships"],
        locations=payload["locations"],
        timeline=payload["timeline"],
        central_conflict=payload["central_conflict"],
        foreshadowing=payload["foreshadowing"],
        source=source,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(story_bible)
    db.commit()
    return story_bible


def _story_bible_prompt(summaries: list[ChapterSummary], evidence_items: list[EvidenceItem]) -> str:
    return (
        "你是 Story Bible Worker。请基于章节结构化摘要和原文证据索引生成项目级故事记忆。\n"
        "硬性规则：只基于输入材料，不直接写剧本，不编造没有证据支撑的设定；不确定时使用空数组。\n"
        "Story Bible 只作为项目记忆和生成约束依据，不直接输出剧本内容，只用于保持人物、关系、地点、时间线和伏笔一致。\n"
        "只输出 JSON object，不要 Markdown，不要解释。\n"
        "JSON schema: title, story_type, tone, logline, theme, main_characters(list), "
        "relationships(list), locations(list), timeline(list), central_conflict, foreshadowing(list)。\n"
        f"chapter_summaries:\n{_summary_block(summaries)}\n\n"
        f"evidence_index:\n{_evidence_block(evidence_items)}"
    )


def _summary_block(summaries: list[ChapterSummary]) -> str:
    return compact_lines(
        (
            json.dumps(
                {
                    "chapter_id": summary.chapter_id,
                    "title": summary.title,
                    "summary": truncate_text(summary.summary, 1200),
                    "key_events": summary.key_events,
                    "characters": summary.characters,
                    "locations": summary.locations,
                    "conflicts": summary.conflicts,
                    "foreshadowing": summary.foreshadowing,
                },
                ensure_ascii=False,
            )
            for summary in summaries
        )
        ,
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
        )
        ,
        8000,
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


def _load_json_object(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("story_bible provider returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("story_bible provider response must be a JSON object")
    return payload


def _validate_story_bible_payload(payload: dict) -> dict:
    validated = {}
    for field in TEXT_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"story_bible field {field} must be a non-empty string")
        validated[field] = value.strip()
    for field in LIST_FIELDS:
        value = payload.get(field)
        if not isinstance(value, list):
            raise RuntimeError(f"story_bible field {field} must be a list")
        validated[field] = value
    return validated
