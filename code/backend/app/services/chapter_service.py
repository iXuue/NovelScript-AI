from dataclasses import dataclass, field
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


HEADING_RE = re.compile(r"^(?:#{1,6}\s*)?((?:第[一二三四五六七八九十百千万0-9]+章|Chapter\s+\d+).*)$", re.I)


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]


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

