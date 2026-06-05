import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.services.llm_provider import LLMProvider, LLMRequest
from app.services.store import now_utc


def generate_chapter_summaries(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None = None,
) -> list[ChapterSummary]:
    db.execute(delete(ChapterSummary).where(ChapterSummary.project_id == project_id))
    timestamp = now_utc()
    summaries: list[ChapterSummary] = []
    chapters = _confirmed_chapters(db, project_id)
    for chapter in chapters:
        paragraphs = _chapter_paragraphs(db, project_id, chapter.chapter_id)
        payload = _generate_summary_payload(chapter, paragraphs, llm_provider)
        summary = ChapterSummary(
            project_id=project_id,
            chapter_id=chapter.chapter_id,
            title=chapter.title,
            summary=payload["summary"],
            key_events=payload["key_events"],
            characters=payload["characters"],
            locations=payload["locations"],
            conflicts=payload["conflicts"],
            foreshadowing=payload["foreshadowing"],
            adaptation_suggestions=payload["adaptation_suggestions"],
            source=payload["source"],
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(summary)
        summaries.append(summary)
    db.commit()
    return summaries


def generate_evidence_index(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None = None,
) -> list[EvidenceItem]:
    db.execute(delete(EvidenceItem).where(EvidenceItem.project_id == project_id))
    timestamp = now_utc()
    evidence_items: list[EvidenceItem] = []
    counter = 1
    chapters = _confirmed_chapters(db, project_id)
    for chapter in chapters:
        paragraphs = _chapter_paragraphs(db, project_id, chapter.chapter_id)
        payloads = _generate_evidence_payloads(chapter, paragraphs, llm_provider)
        valid_paragraph_ids = {paragraph.paragraph_id for paragraph in paragraphs}
        for payload in payloads:
            if payload["paragraph_id"] not in valid_paragraph_ids:
                raise RuntimeError(f"Evidence item references unknown paragraph_id: {payload['paragraph_id']}")
            evidence = EvidenceItem(
                project_id=project_id,
                evidence_id=f"EV{counter:03d}",
                chapter_id=chapter.chapter_id,
                paragraph_id=payload["paragraph_id"],
                quote=payload["quote"],
                evidence_type=payload["evidence_type"],
                explanation=payload["explanation"],
                related_characters=payload["related_characters"],
                related_locations=payload["related_locations"],
                related_plot_points=payload["related_plot_points"],
                importance=payload["importance"],
                must_keep=payload["must_keep"],
                source=payload["source"],
                created_at=timestamp,
                updated_at=timestamp,
            )
            db.add(evidence)
            evidence_items.append(evidence)
            counter += 1
    db.commit()
    return evidence_items


def run_initial_text_analysis(db: Session, project_id: str, llm_provider: LLMProvider | None = None) -> dict:
    summaries = generate_chapter_summaries(db, project_id, llm_provider)
    evidence_items = generate_evidence_index(db, project_id, llm_provider)
    return {"chapter_summary_count": len(summaries), "evidence_count": len(evidence_items)}


def _confirmed_chapters(db: Session, project_id: str) -> list[Chapter]:
    return (
        db.query(Chapter)
        .filter(Chapter.project_id == project_id, Chapter.status == "confirmed")
        .order_by(Chapter.order)
        .all()
    )


def _chapter_paragraphs(db: Session, project_id: str, chapter_id: str) -> list[Paragraph]:
    return (
        db.query(Paragraph)
        .filter(Paragraph.project_id == project_id, Paragraph.chapter_id == chapter_id)
        .order_by(Paragraph.order)
        .all()
    )


def _classify_evidence_type(text: str) -> str:
    if "“" in text or '"' in text:
        return "dialogue"
    if any(keyword in text for keyword in ["想", "心", "觉得", "害怕", "愤怒"]):
        return "psychology"
    return "key_event"


def _generate_summary_payload(
    chapter: Chapter,
    paragraphs: list[Paragraph],
    llm_provider: LLMProvider | None,
) -> dict:
    if llm_provider is None:
        excerpt = " ".join(paragraph.text for paragraph in paragraphs[:2])
        return {
            "summary": excerpt or chapter.raw_text[:300] or f"{chapter.title} 待摘要。",
            "key_events": [paragraph.text for paragraph in paragraphs[:3]],
            "characters": [],
            "locations": [],
            "conflicts": [],
            "foreshadowing": [],
            "adaptation_suggestions": ["保留本章已确认段落中的关键情节。"],
            "source": "deterministic_stub",
        }

    response = llm_provider.generate(
        LLMRequest(
            task_type="chapter_summary",
            prompt=_chapter_summary_prompt(chapter, paragraphs),
            response_format="json",
        )
    )
    data = _load_json_object(response.text, "chapter_summary")
    return {
        "summary": str(data.get("summary") or ""),
        "key_events": _list_value(data.get("key_events")),
        "characters": _list_value(data.get("characters")),
        "locations": _list_value(data.get("locations")),
        "conflicts": _list_value(data.get("conflicts")),
        "foreshadowing": _list_value(data.get("foreshadowing")),
        "adaptation_suggestions": _list_value(data.get("adaptation_suggestions")),
        "source": response.model_name,
    }


def _generate_evidence_payloads(
    chapter: Chapter,
    paragraphs: list[Paragraph],
    llm_provider: LLMProvider | None,
) -> list[dict]:
    if llm_provider is None:
        return [
            {
                "paragraph_id": paragraph.paragraph_id,
                "quote": paragraph.text,
                "evidence_type": _classify_evidence_type(paragraph.text),
                "explanation": f"来自{chapter.title}的原文素材，可作为后续改编依据。",
                "related_characters": [],
                "related_locations": [],
                "related_plot_points": [chapter.title],
                "importance": 3 if index == 1 else 2,
                "must_keep": True,
                "source": "deterministic_stub",
            }
            for index, paragraph in enumerate(paragraphs, start=1)
        ]

    response = llm_provider.generate(
        LLMRequest(
            task_type="evidence_extraction",
            prompt=_evidence_prompt(chapter, paragraphs),
            response_format="json",
        )
    )
    data = _load_json_object(response.text, "evidence_extraction")
    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        raise RuntimeError("evidence_extraction response must contain an evidence list")
    return [
        {
            "paragraph_id": str(item.get("paragraph_id") or ""),
            "quote": str(item.get("quote") or ""),
            "evidence_type": str(item.get("evidence_type") or "关键事件"),
            "explanation": str(item.get("explanation") or ""),
            "related_characters": _list_value(item.get("related_characters")),
            "related_locations": _list_value(item.get("related_locations")),
            "related_plot_points": _list_value(item.get("related_plot_points")),
            "importance": int(item.get("importance") or 1),
            "must_keep": bool(item.get("must_keep")),
            "source": response.model_name,
        }
        for item in evidence
        if isinstance(item, dict)
    ]


def _chapter_summary_prompt(chapter: Chapter, paragraphs: list[Paragraph]) -> str:
    return (
        "请为已确认小说章节生成结构化章节摘要。只基于给定段落，不要编造。\n"
        "输出 JSON 字段：summary, key_events, characters, locations, conflicts, "
        "foreshadowing, adaptation_suggestions。\n"
        f"chapter_id: {chapter.chapter_id}\n"
        f"title: {chapter.title}\n"
        f"paragraphs:\n{_paragraph_block(paragraphs)}"
    )


def _evidence_prompt(chapter: Chapter, paragraphs: list[Paragraph]) -> str:
    return (
        "请从已确认小说章节中提取原文证据索引。每条证据必须引用已有 paragraph_id。\n"
        "输出 JSON：{\"evidence\":[{\"paragraph_id\",\"quote\",\"evidence_type\",\"explanation\","
        "\"related_characters\",\"related_locations\",\"related_plot_points\",\"importance\",\"must_keep\"}]}。\n"
        f"chapter_id: {chapter.chapter_id}\n"
        f"title: {chapter.title}\n"
        f"paragraphs:\n{_paragraph_block(paragraphs)}"
    )


def _paragraph_block(paragraphs: list[Paragraph]) -> str:
    return "\n".join(f"- {paragraph.paragraph_id}: {paragraph.text}" for paragraph in paragraphs)


def _load_json_object(text: str, task_type: str) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{task_type} provider returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"{task_type} provider response must be a JSON object")
    return data


def _list_value(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
