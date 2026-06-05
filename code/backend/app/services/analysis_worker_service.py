from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.services.llm_provider import LLMProvider, LLMRequest
from app.services.store import now_utc


ALLOWED_EVIDENCE_TYPES = {
    "关键事件",
    "对白",
    "人物目标",
    "人物关系",
    "心理描写",
    "视觉元素",
    "线索",
    "伏笔",
    "冲突",
    "地点描写",
}


@dataclass(frozen=True)
class ChapterSnapshot:
    chapter_id: str
    title: str
    raw_text: str


@dataclass(frozen=True)
class ParagraphSnapshot:
    paragraph_id: str
    text: str


def generate_chapter_summaries(
    db: Session,
    project_id: str,
    llm_provider: LLMProvider | None = None,
) -> list[ChapterSummary]:
    db.execute(delete(ChapterSummary).where(ChapterSummary.project_id == project_id))
    timestamp = now_utc()
    summaries: list[ChapterSummary] = []
    chapters = _analysis_snapshots(db, project_id)
    payloads = run_summary_payload_generation(chapters, llm_provider)
    for chapter, payload in payloads:
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
    chapters = _analysis_snapshots(db, project_id)
    payloads_by_chapter = run_evidence_payload_generation(chapters, llm_provider)
    for chapter, paragraphs, payloads in payloads_by_chapter:
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
    chapters = _analysis_snapshots(db, project_id)
    payloads = run_analysis_payload_generation(chapters, llm_provider)
    summaries = _persist_chapter_summaries(db, project_id, payloads["summaries"])
    evidence_items = _persist_evidence_items(db, project_id, payloads["evidence_payloads_by_chapter"])
    return {"chapter_summary_count": len(summaries), "evidence_count": len(evidence_items)}


def run_analysis_payload_generation(
    chapters: list[tuple[ChapterSnapshot, list[ParagraphSnapshot]]],
    llm_provider: LLMProvider | None,
) -> dict:
    if llm_provider is None:
        return {
            "summaries": run_summary_payload_generation(chapters, None),
            "evidence_payloads_by_chapter": run_evidence_payload_generation(chapters, None),
        }

    max_workers = max(1, min(8, len(chapters) * 2))
    summaries: list[tuple[ChapterSnapshot, dict]] = []
    evidence_payloads_by_chapter: list[tuple[ChapterSnapshot, list[ParagraphSnapshot], list[dict]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for chapter, paragraphs in chapters:
            futures[executor.submit(_generate_summary_payload, chapter, paragraphs, llm_provider)] = (
                "summary",
                chapter,
                paragraphs,
            )
            futures[executor.submit(_generate_evidence_payloads, chapter, paragraphs, llm_provider)] = (
                "evidence",
                chapter,
                paragraphs,
            )
        for future in as_completed(futures):
            task_type, chapter, paragraphs = futures[future]
            if task_type == "summary":
                summaries.append((chapter, future.result()))
            else:
                evidence_payloads_by_chapter.append((chapter, paragraphs, future.result()))

    summaries.sort(key=lambda item: item[0].chapter_id)
    evidence_payloads_by_chapter.sort(key=lambda item: item[0].chapter_id)
    return {"summaries": summaries, "evidence_payloads_by_chapter": evidence_payloads_by_chapter}


def run_summary_payload_generation(
    chapters: list[tuple[ChapterSnapshot, list[ParagraphSnapshot]]],
    llm_provider: LLMProvider | None,
) -> list[tuple[ChapterSnapshot, dict]]:
    if llm_provider is None:
        return [(chapter, _generate_summary_payload(chapter, paragraphs, None)) for chapter, paragraphs in chapters]

    summaries: list[tuple[ChapterSnapshot, dict]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(chapters)))) as executor:
        futures = {
            executor.submit(_generate_summary_payload, chapter, paragraphs, llm_provider): chapter
            for chapter, paragraphs in chapters
        }
        for future in as_completed(futures):
            summaries.append((futures[future], future.result()))
    summaries.sort(key=lambda item: item[0].chapter_id)
    return summaries


def run_evidence_payload_generation(
    chapters: list[tuple[ChapterSnapshot, list[ParagraphSnapshot]]],
    llm_provider: LLMProvider | None,
) -> list[tuple[ChapterSnapshot, list[ParagraphSnapshot], list[dict]]]:
    if llm_provider is None:
        return [
            (chapter, paragraphs, _generate_evidence_payloads(chapter, paragraphs, None))
            for chapter, paragraphs in chapters
        ]

    evidence_payloads_by_chapter: list[tuple[ChapterSnapshot, list[ParagraphSnapshot], list[dict]]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(chapters)))) as executor:
        futures = {}
        for chapter, paragraphs in chapters:
            futures[executor.submit(_generate_evidence_payloads, chapter, paragraphs, llm_provider)] = (
                chapter,
                paragraphs,
            )
        for future in as_completed(futures):
            chapter, paragraphs = futures[future]
            evidence_payloads_by_chapter.append((chapter, paragraphs, future.result()))

    evidence_payloads_by_chapter.sort(key=lambda item: item[0].chapter_id)
    return evidence_payloads_by_chapter


def _persist_chapter_summaries(
    db: Session,
    project_id: str,
    summary_payloads: list[tuple[ChapterSnapshot, dict]],
) -> list[ChapterSummary]:
    db.execute(delete(ChapterSummary).where(ChapterSummary.project_id == project_id))
    timestamp = now_utc()
    summaries = []
    for chapter, payload in summary_payloads:
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


def _persist_evidence_items(
    db: Session,
    project_id: str,
    payloads_by_chapter: list[tuple[ChapterSnapshot, list[ParagraphSnapshot], list[dict]]],
) -> list[EvidenceItem]:
    db.execute(delete(EvidenceItem).where(EvidenceItem.project_id == project_id))
    timestamp = now_utc()
    evidence_items = []
    counter = 1
    for chapter, paragraphs, payloads in payloads_by_chapter:
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


def _analysis_snapshots(db: Session, project_id: str) -> list[tuple[ChapterSnapshot, list[ParagraphSnapshot]]]:
    snapshots = []
    for chapter in _confirmed_chapters(db, project_id):
        paragraphs = [
            ParagraphSnapshot(paragraph_id=paragraph.paragraph_id, text=paragraph.text)
            for paragraph in _chapter_paragraphs(db, project_id, chapter.chapter_id)
        ]
        snapshots.append(
            (
                ChapterSnapshot(
                    chapter_id=chapter.chapter_id,
                    title=chapter.title,
                    raw_text=chapter.raw_text,
                ),
                paragraphs,
            )
        )
    return snapshots


def _classify_evidence_type(text: str) -> str:
    if "“" in text or '"' in text:
        return "对白"
    if any(keyword in text for keyword in ["想", "心", "觉得", "害怕", "愤怒"]):
        return "心理描写"
    return "关键事件"


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
    payload = {
        "summary": _required_text(data, "summary", "chapter_summary"),
        "key_events": _required_list(data, "key_events", "chapter_summary"),
        "characters": _required_list(data, "characters", "chapter_summary"),
        "locations": _required_list(data, "locations", "chapter_summary"),
        "conflicts": _required_list(data, "conflicts", "chapter_summary"),
        "foreshadowing": _required_list(data, "foreshadowing", "chapter_summary"),
        "adaptation_suggestions": _required_list(data, "adaptation_suggestions", "chapter_summary"),
        "source": response.model_name,
    }
    return payload


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
    paragraph_text_by_id = {paragraph.paragraph_id: paragraph.text for paragraph in paragraphs}
    payloads = []
    for item in evidence:
        if not isinstance(item, dict):
            raise RuntimeError("evidence_extraction evidence items must be JSON objects")
        paragraph_id = _required_text(item, "paragraph_id", "evidence_extraction")
        quote = _required_text(item, "quote", "evidence_extraction")
        evidence_type = _required_text(item, "evidence_type", "evidence_extraction")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES:
            raise RuntimeError(f"evidence_type must be one of {sorted(ALLOWED_EVIDENCE_TYPES)}")
        source_text = paragraph_text_by_id.get(paragraph_id)
        if source_text is None:
            raise RuntimeError(f"Evidence item references unknown paragraph_id: {paragraph_id}")
        if quote not in source_text:
            raise RuntimeError("quote must be an exact excerpt from the referenced paragraph")
        importance = int(item.get("importance") or 0)
        if importance < 1 or importance > 5:
            raise RuntimeError("importance must be an integer from 1 to 5")
        if not isinstance(item.get("must_keep"), bool):
            raise RuntimeError("must_keep must be a boolean")
        payloads.append(
            {
                "paragraph_id": paragraph_id,
                "quote": quote,
                "evidence_type": evidence_type,
                "explanation": _required_text(item, "explanation", "evidence_extraction"),
                "related_characters": _required_list(item, "related_characters", "evidence_extraction"),
                "related_locations": _required_list(item, "related_locations", "evidence_extraction"),
                "related_plot_points": _required_list(item, "related_plot_points", "evidence_extraction"),
                "importance": importance,
                "must_keep": item["must_keep"],
                "source": response.model_name,
            }
        )
    return payloads


def _chapter_summary_prompt(chapter: Chapter, paragraphs: list[Paragraph]) -> str:
    return (
        "你是小说改编分析 Worker。请为已确认小说章节生成结构化章节摘要。\n"
        "硬性规则：只基于给定段落，不要编造；不能改写原文事实；不确定时使用空数组。\n"
        "必须覆盖：本章发生了什么、关键事件、人物、地点、冲突、伏笔、适合改编的场景、改编建议、遗漏风险。\n"
        "只输出 JSON object，不要 Markdown，不要解释。\n"
        "JSON schema 示例：\n"
        "{\n"
        '  "summary": "非空字符串",\n'
        '  "key_events": ["事件"],\n'
        '  "characters": ["人物"],\n'
        '  "locations": ["地点"],\n'
        '  "conflicts": ["冲突"],\n'
        '  "foreshadowing": ["伏笔"],\n'
        '  "adaptation_suggestions": ["改编建议，包含遗漏风险"]\n'
        "}\n"
        f"chapter_id: {chapter.chapter_id}\n"
        f"title: {chapter.title}\n"
        f"paragraphs:\n{_paragraph_block(paragraphs)}"
    )


def _evidence_prompt(chapter: Chapter, paragraphs: list[Paragraph]) -> str:
    return (
        "你是 Evidence Extraction Worker。请从已确认小说章节中提取可支撑改编的原文证据索引。\n"
        "硬性规则：每条证据必须引用已有 paragraph_id；不得引用不存在的 paragraph_id；"
        "quote 必须是原文摘录，不能改写、概括或补写；不确定时少提取，不要编造。\n"
        "证据类型只能使用：关键事件、对白、人物目标、人物关系、心理描写、视觉元素、线索、伏笔、冲突、地点描写。\n"
        "importance 必须是 1 到 5 的整数；must_keep 必须是 boolean。\n"
        "只输出 JSON object，不要 Markdown，不要解释。\n"
        "JSON schema 示例：\n"
        "{\n"
        '  "evidence": [\n'
        "    {\n"
        '      "paragraph_id": "CH001_P001",\n'
        '      "quote": "原文摘录",\n'
        '      "evidence_type": "关键事件",\n'
        '      "explanation": "这条证据为什么重要",\n'
        '      "related_characters": ["人物"],\n'
        '      "related_locations": ["地点"],\n'
        '      "related_plot_points": ["剧情点"],\n'
        '      "importance": 1,\n'
        '      "must_keep": true\n'
        "    }\n"
        "  ]\n"
        "}\n"
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


def _required_text(data: dict, key: str, task_type: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"{task_type} response field {key} must be a non-empty string")
    return value.strip()


def _required_list(data: dict, key: str, task_type: str) -> list:
    value = data.get(key)
    if not isinstance(value, list):
        raise RuntimeError(f"{task_type} response field {key} must be a list")
    return value
