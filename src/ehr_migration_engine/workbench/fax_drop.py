"""Upload and remove PDFs from the live fax drop (data/01_raw/faxes)."""

from __future__ import annotations

import re
from pathlib import Path

from ehr_migration_engine.workbench.paths import DataLayout, layout_for

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_SUFFIXES = {".pdf"}


def list_faxes(root: Path | None = None) -> list[dict[str, str | int]]:
    layout = layout_for(root)
    layout.faxes.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str | int]] = []
    for path in sorted(layout.faxes.glob("*.pdf")):
        if not path.is_file():
            continue
        rows.append(
            {
                "stem": path.stem,
                "filename": path.name,
                "bytes": path.stat().st_size,
            }
        )
    return rows


def save_upload(filename: str, data: bytes, root: Path | None = None) -> dict[str, str | int]:
    """Save one PDF as the sole live drop packet.

    Clears existing faxes and derived stage files first so Split/OCR only
    process the uploaded scan, not every PDF already sitting in the folder.
    """
    layout = layout_for(root)
    safe = _safe_filename(filename)
    if Path(safe).suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ValueError("Only PDF uploads are supported.")
    if not data:
        raise ValueError("Empty upload.")

    cleared = delete_all_packets(root)
    layout.faxes.mkdir(parents=True, exist_ok=True)
    destination = layout.faxes / safe
    destination.write_bytes(data)
    return {
        "stem": destination.stem,
        "filename": destination.name,
        "bytes": len(data),
        "cleared": int(cleared["count"]),
    }


def delete_packet(stem: str, root: Path | None = None) -> dict[str, object]:
    """Remove a fax PDF and any derived triage/OCR/extract/normalize/FHIR files."""
    packet = _safe_stem(stem)
    layout = layout_for(root)
    removed: list[str] = []

    for path in _packet_paths(layout, packet):
        if path.is_file():
            path.unlink()
            removed.append(str(path.relative_to(layout.root)))

    return {"stem": packet, "removed": removed, "count": len(removed)}


def delete_all_packets(root: Path | None = None) -> dict[str, object]:
    """Clear the fax drop and every derived page artifact under data/."""
    layout = layout_for(root)
    removed: list[str] = []
    for path in _all_drop_artifacts(layout):
        if path.is_file():
            path.unlink()
            try:
                removed.append(str(path.relative_to(layout.root)))
            except ValueError:
                removed.append(path.name)
    return {"removed": removed, "count": len(removed)}


def _packet_paths(layout: DataLayout, packet: str) -> list[Path]:
    paths: list[Path] = []
    for directory, pattern in (
        (layout.faxes, f"{packet}.pdf"),
        (layout.root / "data" / "02_triage" / "unstructured", f"{packet}.pdf"),
        (layout.atomic_pages, f"{packet}_page_*.pdf"),
        (layout.ocr, f"{packet}_page_*.json"),
        (layout.parsed_text, f"{packet}_page_*.txt"),
        (layout.structured, f"{packet}_page_*.json"),
        (layout.structured, f"{packet}_page_*.error.json"),
        (layout.root / "data" / "04_normalized", f"{packet}_page_*.json"),
        (layout.fhir, f"{packet}_page_*.json"),
    ):
        if not directory.is_dir():
            continue
        if "*" in pattern:
            paths.extend(sorted(p for p in directory.glob(pattern) if p.is_file()))
        else:
            candidate = directory / pattern
            if candidate.is_file():
                paths.append(candidate)
    return paths


def _all_drop_artifacts(layout: DataLayout) -> list[Path]:
    paths: list[Path] = []
    for directory, patterns in (
        (layout.faxes, ("*.pdf",)),
        (layout.root / "data" / "02_triage" / "unstructured", ("*.pdf",)),
        (layout.atomic_pages, ("*.pdf",)),
        (layout.ocr, ("*.json",)),
        (layout.parsed_text, ("*.txt",)),
        (layout.structured, ("*.json",)),
        (layout.root / "data" / "04_normalized", ("*.json",)),
        (layout.fhir, ("*.json",)),
    ):
        if not directory.is_dir():
            continue
        for pattern in patterns:
            paths.extend(sorted(p for p in directory.glob(pattern) if p.is_file()))
    return paths


def _safe_filename(name: str) -> str:
    base = Path(name).name
    if not base or base in {".", ".."}:
        raise ValueError("Missing filename.")
    stem = _SAFE_NAME.sub("-", Path(base).stem).strip(".-") or "upload"
    suffix = Path(base).suffix.lower() or ".pdf"
    return f"{stem}{suffix}"


def _safe_stem(stem: str) -> str:
    cleaned = _SAFE_NAME.sub("-", stem.strip()).strip(".-")
    if not cleaned:
        raise ValueError("Invalid packet stem.")
    return cleaned
