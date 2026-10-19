"""Scan fax packets and the artifacts each pipeline stage wrote."""

import re
from dataclasses import dataclass
from pathlib import Path

from .paths import layout_for

BATCH_ID = "local-faxes"
_PAGE_RE = re.compile(r"^(?P<packet>.+)_page_(?P<num>\d+)$")


@dataclass(frozen=True)
class PageArtifacts:
    stem: str
    packet_stem: str
    page_number: int
    packet_pdf: Path | None
    atomic_pdf: Path | None
    ocr_json: Path | None
    parsed_text: Path | None
    structured_json: Path | None
    error_json: Path | None


@dataclass(frozen=True)
class Packet:
    stem: str
    filename: str
    pdf: Path | None
    pages: tuple[PageArtifacts, ...]


@dataclass(frozen=True)
class BatchCatalog:
    batch_id: str
    packets: tuple[Packet, ...]

    def pages(self) -> list[PageArtifacts]:
        return [page for packet in self.packets for page in packet.pages]


def load_catalog(root: Path | None = None) -> BatchCatalog:
    """Build the local fax batch. Missing directories yield an empty batch."""
    layout = layout_for(root)
    packet_pdfs = _pdfs(layout.faxes)
    atomic = _pdfs(layout.atomic_pages)
    ocr = _json_files(layout.ocr)
    parsed = _suffix_files(layout.parsed_text, ".txt")
    structured = _structured_files(layout.structured)
    errors = _error_files(layout.structured)

    stems = set(atomic) | set(ocr) | set(parsed) | set(structured) | set(errors)
    pages_by_packet: dict[str, list[PageArtifacts]] = {stem: [] for stem in packet_pdfs}

    for stem in stems:
        packet_stem, page_number = _split_stem(stem)
        packet_pdf = packet_pdfs.get(packet_stem)
        pages_by_packet.setdefault(packet_stem, []).append(
            PageArtifacts(
                stem=stem,
                packet_stem=packet_stem,
                page_number=page_number,
                packet_pdf=packet_pdf,
                atomic_pdf=atomic.get(stem),
                ocr_json=ocr.get(stem),
                parsed_text=parsed.get(stem),
                structured_json=structured.get(stem),
                error_json=errors.get(stem),
            )
        )

    packets: list[Packet] = []
    for packet_stem in sorted(pages_by_packet):
        pdf = packet_pdfs.get(packet_stem)
        pages = tuple(
            sorted(pages_by_packet[packet_stem], key=lambda page: (page.page_number, page.stem))
        )
        packets.append(
            Packet(
                stem=packet_stem,
                filename=pdf.name if pdf else f"{packet_stem}.pdf",
                pdf=pdf,
                pages=pages,
            )
        )

    return BatchCatalog(batch_id=BATCH_ID, packets=tuple(packets))


def _split_stem(stem: str) -> tuple[str, int]:
    match = _PAGE_RE.match(stem)
    if not match:
        return stem, 0
    return match.group("packet"), int(match.group("num"))


def _pdfs(directory: Path) -> dict[str, Path]:
    return _suffix_files(directory, ".pdf")


def _suffix_files(directory: Path, suffix: str) -> dict[str, Path]:
    if not directory.is_dir():
        return {}
    found: dict[str, Path] = {}
    for path in directory.glob(f"*{suffix}"):
        if path.is_file():
            found[path.stem] = path
    return found


def _json_files(directory: Path) -> dict[str, Path]:
    """JSON files directly in a stage directory, not in subfolders."""
    if not directory.is_dir():
        return {}
    return {path.stem: path for path in directory.glob("*.json") if path.is_file()}


def _structured_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        return {}
    found: dict[str, Path] = {}
    for path in directory.glob("*.json"):
        if path.is_file() and not path.name.endswith(".error.json"):
            found[path.stem] = path
    return found


def _error_files(directory: Path) -> dict[str, Path]:
    if not directory.is_dir():
        return {}
    found: dict[str, Path] = {}
    for path in directory.glob("*.error.json"):
        if path.is_file():
            found[path.name.removesuffix(".error.json")] = path
    return found
