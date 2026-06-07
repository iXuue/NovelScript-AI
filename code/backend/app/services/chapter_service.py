from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class Paragraph:
    paragraph_id: str
    text: str


@dataclass
class DetectedChapter:
    chapter_id: str
    title: str
    order: int
    raw_text: str
    paragraphs: list[Paragraph] = field(default_factory=list)

    @property
    def paragraph_count(self) -> int:
        return len(split_paragraphs(self.raw_text)) if not self.paragraphs else len(self.paragraphs)

    def to_draft(self) -> dict:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "order": self.order,
            "paragraph_count": self.paragraph_count,
        }


@dataclass(frozen=True)
class UploadedMarkdownDocument:
    filename: str
    markdown: str


HEADING_RE = re.compile(
    r"^(?:#{1,6}\s*)?("
    r"(?:第[一二三四五六七八九十百千万两0-9]+章.*)|"
    r"(?:Chapter\s+\d+\b.*)|"
    r"(?:[一二三四五六七八九十]+、\S.*)|"
    r"(?:\d+[.．]\s*\S.*)|"
    r"(?:序章|楔子|番外(?:\s+\S.*)?)"
    r")$",
    re.I,
)
NATURAL_SORT_RE = re.compile(r"(\d+)")
TOC_MIN_REPEATED_CHAPTERS = 3
TOC_SHORT_CHAPTER_CHARS = 80
TOC_SHORT_CHAPTER_RATIO = 0.8


def split_paragraphs(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    # 先尝试按空行分隔
    if "\n\n" in text:
        return [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    # 没有空行时，每行作为一个段落
    return [line.strip() for line in text.splitlines() if line.strip()]


def natural_sort_key(value: str) -> list[int | str]:
    parts: list[int | str] = []
    for part in NATURAL_SORT_RE.split(value):
        if part.isdigit():
            parts.append(int(part))
        elif part:
            parts.append(part.lower())
    return parts


def detect_chapters(markdown: str) -> list[DetectedChapter]:
    chapters: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        match = HEADING_RE.match(line)
        if match:
            if current_title is not None:
                chapters.append((current_title, current_lines))
            current_title = match.group(1).strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(raw_line)

    if current_title is not None:
        chapters.append((current_title, current_lines))

    if not chapters:
        chapters.append(("正文", [markdown]))

    return [
        DetectedChapter(
            chapter_id=f"CH{index:03d}",
            title=title,
            order=index,
            raw_text="\n".join(lines).strip(),
        )
        for index, (title, lines) in enumerate(chapters, start=1)
    ]


def detect_documents_chapters(documents: list[UploadedMarkdownDocument]) -> list[DetectedChapter]:
    detected: list[DetectedChapter] = []
    for document in sorted(documents, key=lambda item: natural_sort_key(item.filename)):
        document_chapters = _drop_table_of_contents_chapters(detect_chapters(document.markdown))
        if len(document_chapters) == 1 and document_chapters[0].title == "正文":
            document_chapters[0].title = Path(document.filename).stem
        detected.extend(document_chapters)

    return [
        DetectedChapter(
            chapter_id=f"CH{index:03d}",
            title=chapter.title,
            order=index,
            raw_text=chapter.raw_text,
        )
        for index, chapter in enumerate(detected, start=1)
    ]


def _drop_table_of_contents_chapters(chapters: list[DetectedChapter]) -> list[DetectedChapter]:
    if len(chapters) < TOC_MIN_REPEATED_CHAPTERS * 2:
        return chapters

    title_keys = [_chapter_title_key(chapter.title) for chapter in chapters]
    drop_count = 0
    for duplicate_start in range(TOC_MIN_REPEATED_CHAPTERS, len(chapters) - TOC_MIN_REPEATED_CHAPTERS + 1):
        repeated_count = 0
        while (
            repeated_count < duplicate_start
            and duplicate_start + repeated_count < len(chapters)
            and title_keys[repeated_count] == title_keys[duplicate_start + repeated_count]
        ):
            repeated_count += 1

        if repeated_count >= TOC_MIN_REPEATED_CHAPTERS and _looks_like_table_of_contents(chapters[:repeated_count]):
            drop_count = max(drop_count, repeated_count)

    return chapters[drop_count:] if drop_count else chapters


def _chapter_title_key(title: str) -> str:
    normalized = re.sub(r"\s+", "", title).lower()
    marker = re.match(r"(第[一二三四五六七八九十百千万两0-9]+章|chapter\d+)", normalized, re.I)
    return marker.group(1).lower() if marker else normalized


def _looks_like_table_of_contents(chapters: list[DetectedChapter]) -> bool:
    if len(chapters) < TOC_MIN_REPEATED_CHAPTERS:
        return False
    lengths = sorted(len(chapter.raw_text.strip()) for chapter in chapters)
    short_count = sum(length <= TOC_SHORT_CHAPTER_CHARS for length in lengths)
    median_length = lengths[len(lengths) // 2]
    return short_count / len(lengths) >= TOC_SHORT_CHAPTER_RATIO or median_length <= TOC_SHORT_CHAPTER_CHARS


def assign_paragraph_ids(chapters: list[DetectedChapter]) -> list[DetectedChapter]:
    indexed: list[DetectedChapter] = []
    for chapter in chapters:
        paragraphs = [
            Paragraph(paragraph_id=f"{chapter.chapter_id}_P{idx:03d}", text=text)
            for idx, text in enumerate(split_paragraphs(chapter.raw_text), start=1)
        ]
        indexed.append(
            DetectedChapter(
                chapter_id=chapter.chapter_id,
                title=chapter.title,
                order=chapter.order,
                raw_text=chapter.raw_text,
                paragraphs=paragraphs,
            )
        )
    return indexed

