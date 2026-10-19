import json
from pathlib import Path

import pytest

from ehr_migration_engine.workbench.review import ReviewLedger


def test_correction_is_appended_and_source_json_is_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "data" / "04_structured" / "packet_001_scanned_page_001.json"
    source.parent.mkdir(parents=True)
    source.write_text(
        json.dumps({"patient_name": "Ada", "conditions": [], "medications": []}),
        encoding="utf-8",
    )
    before = source.read_bytes()
    ledger = ReviewLedger(tmp_path / "data" / "06_review" / "ledger.jsonl")

    with pytest.raises(ValueError, match="reason"):
        ledger.record(
            stem="packet_001_scanned_page_001",
            field_path="patient_name",
            status="corrected",
            original_value="Ada",
            revised_value="Ada Lovelace",
            reason="  ",
        )
    assert not ledger.path.exists()
    assert source.read_bytes() == before

    ledger.record(
        stem="packet_001_scanned_page_001",
        field_path="patient_name",
        status="corrected",
        original_value="Ada",
        revised_value="Ada Lovelace",
        reason="Expanded the given name",
        timestamp="2026-10-20T00:00:00+00:00",
    )
    ledger.record(
        stem="packet_001_scanned_page_001",
        field_path="conditions[0].diagnosis",
        status="rejected",
        original_value="Hypertension",
        reason="Not supported by the page",
        timestamp="2026-10-20T00:01:00+00:00",
    )

    assert source.read_bytes() == before
    entries = ledger.entries()
    assert len(entries) == 2
    assert entries[0].revised_value == "Ada Lovelace"
    assert entries[0].original_value == "Ada"
    assert entries[1].status == "rejected"
    latest = ledger.latest_for("packet_001_scanned_page_001")
    assert latest["patient_name"].status == "corrected"
    assert len(ledger.path.read_text(encoding="utf-8").splitlines()) == 2
