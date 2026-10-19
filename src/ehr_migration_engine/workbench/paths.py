"""Locations of pipeline artifacts on disk."""

import json
from dataclasses import dataclass
from pathlib import Path

# src/ehr_migration_engine/workbench/paths.py -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class DataLayout:
    root: Path

    @property
    def faxes(self) -> Path:
        return self.root / "data" / "01_raw" / "faxes"

    @property
    def atomic_pages(self) -> Path:
        return self.root / "data" / "02_triage" / "atomic_pages"

    @property
    def ocr(self) -> Path:
        return self.root / "data" / "03_ocr"

    @property
    def parsed_text(self) -> Path:
        return self.ocr / "parsed_text"

    @property
    def structured(self) -> Path:
        return self.root / "data" / "04_structured"

    @property
    def ledger(self) -> Path:
        return self.root / "data" / "06_review" / "ledger.jsonl"


def layout_for(root: Path | None = None) -> DataLayout:
    return DataLayout(root or PROJECT_ROOT)


def read_json(path: Path | None) -> dict | list | None:
    """Load a JSON file. Missing or unreadable files return None."""
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
