import json
from pathlib import Path

from ehr_migration_engine.extraction.failures import clear_extraction_error, write_extraction_error


def test_error_sidecar_records_the_failure_without_a_note_field(tmp_path: Path) -> None:
    path = write_extraction_error(
        tmp_path,
        "packet_001_scanned_page_004",
        3,
        "schema",
        "Schema mismatch. " + ("x" * 800),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "packet_001_scanned_page_004.error.json"
    assert set(payload) == {"stem", "attempts", "error_type", "message"}
    assert payload["stem"] == "packet_001_scanned_page_004"
    assert payload["attempts"] == 3
    assert payload["error_type"] == "schema"
    assert len(payload["message"]) == 500
    assert "note" not in payload

    clear_extraction_error(tmp_path, "packet_001_scanned_page_004")
    assert not path.exists()
