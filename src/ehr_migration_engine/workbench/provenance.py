"""Link an extracted string to the OCR block that contains it."""

from dataclasses import dataclass

from ehr_migration_engine.vision.spatial_parser import clean_html_to_text

from .facts import Fact

_MIN_NEEDLE = 2


@dataclass(frozen=True)
class ProvenanceLink:
    field_path: str
    value: str
    resolved: bool
    source_file: str | None
    page_number: int | None
    block_index: int | None
    reading_order: int | None
    block_text: str | None
    bbox: tuple[float, float, float, float] | None
    confidence: float | None
    label: str | None


def link_facts(
    ocr: dict | None,
    facts: list[Fact],
    *,
    source_file: str | None,
    page_number: int | None,
) -> list[ProvenanceLink]:
    """Match each fact to a block. Unmatched facts stay unresolved."""
    blocks = ocr.get("blocks") if isinstance(ocr, dict) else None
    if not isinstance(blocks, list):
        return [_unresolved(fact, source_file, page_number) for fact in facts]

    links: list[ProvenanceLink] = []
    for fact in facts:
        links.append(_match_fact(fact, blocks, source_file, page_number))
    return links


def source_frame(ocr: dict | None) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Return ((x0, y0), (width, height)) for the OCR image, when the file records it."""
    if not isinstance(ocr, dict):
        return None
    bbox = as_bbox(ocr.get("image_bbox"))
    if bbox is not None:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width > 0 and height > 0:
            return (bbox[0], bbox[1]), (width, height)

    width = _positive_number(ocr.get("width") or ocr.get("image_width"))
    height = _positive_number(ocr.get("height") or ocr.get("image_height"))
    if width is not None and height is not None:
        return (0.0, 0.0), (width, height)
    return None


def scale_bbox(
    bbox: tuple[float, float, float, float],
    origin: tuple[float, float],
    source_size: tuple[float, float],
    target_size: tuple[float, float],
) -> tuple[float, float, float, float]:
    """Map OCR image coordinates onto a rendered page."""
    scale_x = target_size[0] / source_size[0]
    scale_y = target_size[1] / source_size[1]
    return (
        (bbox[0] - origin[0]) * scale_x,
        (bbox[1] - origin[1]) * scale_y,
        (bbox[2] - origin[0]) * scale_x,
        (bbox[3] - origin[1]) * scale_y,
    )


def as_bbox(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return tuple(float(part) for part in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _match_fact(
    fact: Fact,
    blocks: list,
    source_file: str | None,
    page_number: int | None,
) -> ProvenanceLink:
    needle = _norm(fact.value)
    if len(needle) < _MIN_NEEDLE:
        return _unresolved(fact, source_file, page_number)

    candidates: list[tuple[int, int, ProvenanceLink]] = []
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        text = _block_text(block)
        if needle not in _norm(text):
            continue
        line = _matching_line(block, needle)
        line_text = _line_text(line) if line else None
        weight = len(_norm(line_text or text))
        bbox = as_bbox(line.get("bbox")) if line else None
        if bbox is None:
            bbox = as_bbox(block.get("bbox"))
        reading_order = block.get("reading_order")
        candidates.append(
            (
                weight,
                index,
                ProvenanceLink(
                    field_path=fact.field_path,
                    value=fact.value,
                    resolved=True,
                    source_file=source_file,
                    page_number=page_number,
                    block_index=index,
                    reading_order=reading_order if isinstance(reading_order, int) else None,
                    block_text=text,
                    bbox=bbox,
                    confidence=_confidence(line, block),
                    label=_text(block.get("label")),
                ),
            )
        )

    if not candidates:
        return _unresolved(fact, source_file, page_number)
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _unresolved(fact: Fact, source_file: str | None, page_number: int | None) -> ProvenanceLink:
    return ProvenanceLink(
        field_path=fact.field_path,
        value=fact.value,
        resolved=False,
        source_file=source_file,
        page_number=page_number,
        block_index=None,
        reading_order=None,
        block_text=None,
        bbox=None,
        confidence=None,
        label=None,
    )


def _block_text(block: dict) -> str:
    html = block.get("html")
    if isinstance(html, str) and html.strip():
        return clean_html_to_text(html)
    lines = block.get("text_lines")
    if isinstance(lines, list):
        parts = [_line_text(line) for line in lines]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _matching_line(block: dict, needle: str) -> dict | None:
    lines = block.get("text_lines")
    if not isinstance(lines, list):
        return None
    matches = []
    for line in lines:
        if not isinstance(line, dict):
            continue
        text = _line_text(line)
        if text and needle in _norm(text):
            matches.append((len(_norm(text)), line))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def _line_text(line: dict | None) -> str:
    if not isinstance(line, dict):
        return ""
    text = line.get("text")
    return text.strip() if isinstance(text, str) else ""


def _confidence(line: dict | None, block: dict) -> float | None:
    """Prefer the matched line's score. This Surya build stores the score on the block."""
    if isinstance(line, dict):
        score = _score(line.get("confidence"))
        if score is not None:
            return score
    return _score(block.get("confidence"))


def _score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number > 0 else None
