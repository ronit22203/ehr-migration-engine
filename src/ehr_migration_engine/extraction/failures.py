"""Sidecar written when deterministic extraction does not accept a note."""

import json
from pathlib import Path

MESSAGE_LIMIT = 500


def write_extraction_error(
    directory: Path,
    stem: str,
    attempts: int,
    error_type: str,
    message: str,
) -> Path:
    """Record why a note failed. The source note is not copied into this file."""
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "stem": stem,
        "attempts": attempts,
        "error_type": error_type,
        "message": message.strip()[:MESSAGE_LIMIT],
    }
    path = directory / f"{stem}.error.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def clear_extraction_error(directory: Path, stem: str) -> None:
    path = directory / f"{stem}.error.json"
    if path.is_file():
        path.unlink()
