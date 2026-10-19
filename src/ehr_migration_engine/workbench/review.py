"""Append-only review ledger. Source extraction JSON is never rewritten."""

import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

STATUSES = ("pending_review", "accepted", "rejected", "corrected")


@dataclass(frozen=True)
class ReviewEntry:
    stem: str
    field_path: str
    status: str
    original_value: str | None
    revised_value: str | None
    code_system: str | None
    code: str | None
    display: str | None
    reason: str | None
    timestamp: str


_ENTRY_FIELDS = {item.name for item in fields(ReviewEntry)}


class ReviewLedger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(
        self,
        *,
        stem: str,
        field_path: str,
        status: str,
        original_value: str | None,
        revised_value: str | None = None,
        code_system: str | None = None,
        code: str | None = None,
        display: str | None = None,
        reason: str | None = None,
        timestamp: str | None = None,
    ) -> ReviewEntry:
        if status not in STATUSES:
            raise ValueError(f"Unknown review status: {status}")
        reason = _blank_to_none(reason)
        revised_value = _blank_to_none(revised_value)
        if status == "corrected":
            if not reason:
                raise ValueError("A correction requires a reason.")
            if not revised_value:
                raise ValueError("A correction requires a revised value.")
        if status == "rejected" and not reason:
            raise ValueError("A rejection requires a reason.")

        entry = ReviewEntry(
            stem=stem,
            field_path=field_path,
            status=status,
            original_value=original_value,
            revised_value=revised_value,
            code_system=_blank_to_none(code_system),
            code=_blank_to_none(code),
            display=_blank_to_none(display),
            reason=reason,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def entries(self) -> list[ReviewEntry]:
        if not self.path.is_file():
            return []
        found: list[ReviewEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                found.append(ReviewEntry(**{key: payload[key] for key in _ENTRY_FIELDS}))
            except KeyError:
                continue
        return found

    def latest_for(self, stem: str) -> dict[str, ReviewEntry]:
        latest: dict[str, ReviewEntry] = {}
        for entry in self.entries():
            if entry.stem == stem:
                latest[entry.field_path] = entry
        return latest

    def by_stem(self) -> dict[str, dict[str, ReviewEntry]]:
        grouped: dict[str, dict[str, ReviewEntry]] = {}
        for entry in self.entries():
            grouped.setdefault(entry.stem, {})
            grouped[entry.stem][entry.field_path] = entry
        return grouped


def effective_value(original: str, entry: ReviewEntry | None) -> str:
    """Corrected text for display and delivery. The original stays on the entry."""
    if entry and entry.status == "corrected" and entry.revised_value:
        return entry.revised_value
    return original


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
