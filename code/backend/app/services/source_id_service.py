import re


PARAGRAPH_ID_RE = re.compile(r"^CH(\d+)_P(\d+)$")
PARAGRAPH_ID_ALT_SUFFIX_RE = re.compile(r"^(CH\d+_P\d+)_ALT$")


def normalize_paragraph_id(paragraph_id: str, known_paragraph_ids: set[str]) -> str:
    cleaned = paragraph_id.strip()
    if cleaned in known_paragraph_ids:
        return cleaned
    alt_suffix_match = PARAGRAPH_ID_ALT_SUFFIX_RE.fullmatch(cleaned)
    if alt_suffix_match is not None:
        normalized_base = normalize_paragraph_id(alt_suffix_match.group(1), known_paragraph_ids)
        if normalized_base in known_paragraph_ids:
            return normalized_base
    match = PARAGRAPH_ID_RE.fullmatch(cleaned)
    if match is None:
        return cleaned
    normalized = f"CH{int(match.group(1)):03d}_P{int(match.group(2)):03d}"
    return normalized if normalized in known_paragraph_ids else cleaned


def normalize_paragraph_ids(paragraph_ids: list[str], known_paragraph_ids: set[str]) -> list[str]:
    return [normalize_paragraph_id(paragraph_id, known_paragraph_ids) for paragraph_id in paragraph_ids]
