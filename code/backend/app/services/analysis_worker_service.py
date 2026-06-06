from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.analysis import ChapterSummary, EvidenceItem
from app.models.chapter import Chapter, Paragraph
from app.services.context_budget_service import (
    DEFAULT_MAX_ANALYSIS_CHUNK_CHARS,
    DEFAULT_MAX_LLM_PROMPT_CHARS,
    DEFAULT_MAX_QUOTE_CHARS,
    chunk_items_by_text,
    generate_with_context_log,
    truncate_text,
)
from app.services.llm_provider import LLMProvider
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
    run_id: str | None = None,
) -> list[ChapterSummary]:
    db.execute(delete(ChapterSummary).where(ChapterSummary.project_id == project_id))
    timestamp = now_utc()
    summaries: list[ChapterSummary] = []
    chapters = _analysis_snapshots(db, project_id)
    payloads = run_summary_payload_generation(chapters, llm_provider, db=db, project_id=project_id, run_id=run_id)
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
    payloads_by_chapter = run_evidence_payload_generation(chapters, llm_provider, db=db, project_id=project_id)
    for chapter, paragraphs, payloads in payloads_by_chapter:
        valid_paragraph_ids = {paragraph.paragraph_id for paragraph in paragraphs}
        for payload in payloads:
            paragraph_ids = payload["paragraph_ids"]
            unknown_paragraph_ids = set(paragraph_ids) - valid_paragraph_ids
            if unknown_paragraph_ids:
                raise RuntimeError(f"Evidence item references unknown paragraph_ids: {sorted(unknown_paragraph_ids)}")
            evidence = EvidenceItem(
                project_id=project_id,
                evidence_id=f"EV{counter:03d}",
                chapter_id=chapter.chapter_id,
                paragraph_id=paragraph_ids[0],
                paragraph_ids=paragraph_ids,
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
    payloads = run_analysis_payload_generation(chapters, llm_provider, db=db, project_id=project_id)
    summaries = _persist_chapter_summaries(db, project_id, payloads["summaries"])
    evidence_items = _persist_evidence_items(db, project_id, payloads["evidence_payloads_by_chapter"])
    return {"chapter_summary_count": len(summaries), "evidence_count": len(evidence_items)}


def run_analysis_payload_generation(
    chapters: list[tuple[ChapterSnapshot, list[ParagraphSnapshot]]],
    llm_provider: LLMProvider | None,
    db=None,
    project_id: str | None = None,
) -> dict:
    if llm_provider is None:
        return {
            "summaries": run_summary_payload_generation(chapters, None, db=db, project_id=project_id),
            "evidence_payloads_by_chapter": run_evidence_payload_generation(chapters, None, db=db, project_id=project_id),
        }

    if db is not None:
        return {
            "summaries": run_summary_payload_generation(chapters, llm_provider, db=db, project_id=project_id),
            "evidence_payloads_by_chapter": run_evidence_payload_generation(
                chapters,
                llm_provider,
                db=db,
                project_id=project_id,
            ),
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
    db=None,
    project_id: str | None = None,
    run_id: str | None = None,
) -> list[tuple[ChapterSnapshot, dict]]:
    if llm_provider is None:
        return [(chapter, _generate_summary_payload(chapter, paragraphs, None)) for chapter, paragraphs in chapters]

    if db is not None:
        return [
            (chapter, _generate_summary_payload(chapter, paragraphs, llm_provider, db=db, project_id=project_id, run_id=run_id))
            for chapter, paragraphs in chapters
        ]

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
    db=None,
    project_id: str | None = None,
) -> list[tuple[ChapterSnapshot, list[ParagraphSnapshot], list[dict]]]:
    if llm_provider is None:
        return [
            (chapter, paragraphs, _generate_evidence_payloads(chapter, paragraphs, None))
            for chapter, paragraphs in chapters
        ]

    if db is not None:
        return [
            (
                chapter,
                paragraphs,
                _generate_evidence_payloads(chapter, paragraphs, llm_provider, db=db, project_id=project_id),
            )
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
            paragraph_ids = payload["paragraph_ids"]
            unknown_paragraph_ids = set(paragraph_ids) - valid_paragraph_ids
            if unknown_paragraph_ids:
                raise RuntimeError(f"Evidence item references unknown paragraph_ids: {sorted(unknown_paragraph_ids)}")
            evidence = EvidenceItem(
                project_id=project_id,
                evidence_id=f"EV{counter:03d}",
                chapter_id=chapter.chapter_id,
                paragraph_id=paragraph_ids[0],
                paragraph_ids=paragraph_ids,
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
    db=None,
    project_id: str | None = None,
    run_id: str | None = None,
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

    payloads = []
    model_names = []
    chunks = _paragraph_chunks(paragraphs)
    for chunk_index, chunk in enumerate(chunks, start=1):
        response = generate_with_context_log(
            llm_provider,
            task_type="chapter_summary",
            prompt=_chapter_summary_prompt(chapter, chunk),
            response_format="json",
            db=db,
            project_id=project_id,
            run_id=run_id,
            step_type="chapter_summary",
            chunk_range=_chunk_range(chapter.chapter_id, chunk_index, len(chunks), chunk),
            source_item_count=len(paragraphs),
            included_item_count=len(chunk),
            max_chars=DEFAULT_MAX_LLM_PROMPT_CHARS,
        )
        model_names.append(response.model_name)
        data = _load_json_object(response.text, "chapter_summary")
        payloads.append(
            {
                "summary": _required_text(data, "summary", "chapter_summary"),
                "key_events": _required_list(data, "key_events", "chapter_summary"),
                "characters": _required_list(data, "characters", "chapter_summary"),
                "locations": _required_list(data, "locations", "chapter_summary"),
                "conflicts": _required_list(data, "conflicts", "chapter_summary"),
                "foreshadowing": _required_list(data, "foreshadowing", "chapter_summary"),
                "adaptation_suggestions": _required_list(data, "adaptation_suggestions", "chapter_summary"),
            }
        )
    return _merge_summary_payloads(payloads, ",".join(sorted(set(model_names))) or "unknown")


def _generate_evidence_payloads(
    chapter: Chapter,
    paragraphs: list[Paragraph],
    llm_provider: LLMProvider | None,
    db=None,
    project_id: str | None = None,
) -> list[dict]:
    if llm_provider is None:
        return [
            {
                "paragraph_ids": [paragraph.paragraph_id],
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

    payloads = []
    chunks = _paragraph_chunks(paragraphs)
    for chunk_index, chunk in enumerate(chunks, start=1):
        response = generate_with_context_log(
            llm_provider,
            task_type="evidence_extraction",
            prompt=_evidence_prompt(chapter, chunk),
            response_format="json",
            db=db,
            project_id=project_id,
            step_type="evidence_extraction",
            chunk_range=_chunk_range(chapter.chapter_id, chunk_index, len(chunks), chunk),
            source_item_count=len(paragraphs),
            included_item_count=len(chunk),
            max_chars=DEFAULT_MAX_LLM_PROMPT_CHARS,
        )
        payloads.extend(_parse_evidence_payloads(response.text, response.model_name, chunk))
    return payloads


def _paragraph_chunks(paragraphs: list[Paragraph]) -> list[list[Paragraph]]:
    return chunk_items_by_text(paragraphs, lambda paragraph: paragraph.text, DEFAULT_MAX_ANALYSIS_CHUNK_CHARS) or [[]]


def _chunk_range(chapter_id: str, chunk_index: int, chunk_count: int, paragraphs: list[Paragraph]) -> dict:
    return {
        "chapter_id": chapter_id,
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "first_paragraph_id": paragraphs[0].paragraph_id if paragraphs else None,
        "last_paragraph_id": paragraphs[-1].paragraph_id if paragraphs else None,
    }


def _merge_unique(items: list) -> list:
    result = []
    seen = set()
    for item in items:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if marker not in seen:
            seen.add(marker)
            result.append(item)
    return result[:80]


def _merge_summary_payloads(payloads: list[dict], source: str) -> dict:
    return {
        "summary": truncate_text("\n".join(payload["summary"] for payload in payloads if payload.get("summary")), 4000),
        "key_events": _merge_unique([item for payload in payloads for item in payload["key_events"]]),
        "characters": _merge_unique([item for payload in payloads for item in payload["characters"]]),
        "locations": _merge_unique([item for payload in payloads for item in payload["locations"]]),
        "conflicts": _merge_unique([item for payload in payloads for item in payload["conflicts"]]),
        "foreshadowing": _merge_unique([item for payload in payloads for item in payload["foreshadowing"]]),
        "adaptation_suggestions": _merge_unique(
            [item for payload in payloads for item in payload["adaptation_suggestions"]]
        ),
        "source": source,
    }


def _parse_evidence_payloads(text: str, source: str, paragraphs: list[Paragraph]) -> list[dict]:
    data = _load_json_object(text, "evidence_extraction")
    evidence = data.get("evidence")
    if not isinstance(evidence, list):
        raise RuntimeError("evidence_extraction response must contain an evidence list")
    paragraph_text_by_id = {paragraph.paragraph_id: paragraph.text for paragraph in paragraphs}
    payloads = []
    for item in evidence:
        if not isinstance(item, dict):
            raise RuntimeError("evidence_extraction evidence items must be JSON objects")
        paragraph_ids = _paragraph_ids_from_item(item)
        quote = truncate_text(_required_text(item, "quote", "evidence_extraction"), DEFAULT_MAX_QUOTE_CHARS, "")
        evidence_type = _required_text(item, "evidence_type", "evidence_extraction")
        if evidence_type not in ALLOWED_EVIDENCE_TYPES:
            raise RuntimeError(f"evidence_type must be one of {sorted(ALLOWED_EVIDENCE_TYPES)}")
        source_text = _joined_source_text(paragraph_ids, paragraph_text_by_id)
        if source_text is None:
            source_text = _best_match_source(quote, paragraph_text_by_id)
            if source_text is None:
                raise RuntimeError(f"Evidence item references unknown paragraph_ids: {paragraph_ids}")
            paragraph_ids = [source_text[0]]
            source_text = source_text[1]
        if _fuzzy_match(quote, source_text) < 0.5:
            raise RuntimeError("quote must match the referenced paragraph text")
        importance = int(item.get("importance") or 0)
        if importance < 1 or importance > 5:
            raise RuntimeError("importance must be an integer from 1 to 5")
        if not isinstance(item.get("must_keep"), bool):
            raise RuntimeError("must_keep must be a boolean")
        payloads.append(
            {
                "paragraph_ids": paragraph_ids,
                "quote": quote,
                "evidence_type": evidence_type,
                "explanation": _required_text(item, "explanation", "evidence_extraction"),
                "related_characters": _required_list(item, "related_characters", "evidence_extraction"),
                "related_locations": _required_list(item, "related_locations", "evidence_extraction"),
                "related_plot_points": _required_list(item, "related_plot_points", "evidence_extraction"),
                "importance": importance,
                "must_keep": item["must_keep"],
                "source": source,
            }
        )
    return payloads


def _paragraph_ids_from_item(item: dict) -> list[str]:
    paragraph_ids = item.get("paragraph_ids")
    if paragraph_ids is None and item.get("paragraph_id") is not None:
        paragraph_ids = [item["paragraph_id"]]
    if not isinstance(paragraph_ids, list) or not paragraph_ids:
        raise RuntimeError("evidence_extraction response field paragraph_ids must be a non-empty list")
    cleaned = []
    for paragraph_id in paragraph_ids:
        if not isinstance(paragraph_id, str) or not paragraph_id.strip():
            raise RuntimeError("evidence_extraction paragraph_ids must contain non-empty strings")
        cleaned.append(paragraph_id.strip())
    return cleaned


def _joined_source_text(paragraph_ids: list[str], paragraph_text_by_id: dict[str, str]) -> str | None:
    texts = []
    for paragraph_id in paragraph_ids:
        text = paragraph_text_by_id.get(paragraph_id)
        if text is None:
            return None
        texts.append(text)
    return "\n".join(texts)


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
        "硬性规则：每条证据必须引用已有 paragraph_ids 数组；不得引用不存在的 paragraph_ids；"
        "quote 必须是原文摘录，不能改写、概括或补写；不确定时少提取，不要编造。\n"
        "证据类型只能使用：关键事件、对白、人物目标、人物关系、心理描写、视觉元素、线索、伏笔、冲突、地点描写。\n"
        "importance 必须是 1 到 5 的整数；must_keep 必须是 boolean。\n"
        "只输出 JSON object，不要 Markdown，不要解释。\n"
        "JSON schema 示例：\n"
        "{\n"
        '  "evidence": [\n'
        "    {\n"
        '      "paragraph_ids": ["CH001_P001"],\n'
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


def _fuzzy_match(quote: str, source: str) -> float:
    """Return a similarity ratio between 0.0 and 1.0."""
    quote = quote.strip()
    source = source.strip()
    if not quote or not source:
        return 0.0
    if quote in source:
        return 1.0
    char_count = sum(1 for c in quote if c in source)
    return char_count / max(len(quote), 1)


def _best_match_source(quote: str, by_id: dict[str, str]) -> tuple[str, str] | None:
    """Find the paragraph whose text best matches the given quote."""
    best_id, best_text, best_score = None, None, 0.0
    for pid, text in by_id.items():
        score = _fuzzy_match(quote, text)
        if score > best_score:
            best_id, best_text, best_score = pid, text, score
    if best_score >= 0.5:
        return best_id, best_text
    return None
