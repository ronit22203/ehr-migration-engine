import json
from pathlib import Path

from ehr_migration_engine.workbench.catalog import load_catalog


def test_missing_directories_are_an_empty_batch(tmp_path: Path) -> None:
    catalog = load_catalog(tmp_path)

    assert catalog.batch_id == "local-faxes"
    assert catalog.packets == ()


def test_joins_pages_to_artifacts_and_ignores_error_sidecars(tmp_path: Path) -> None:
    faxes = tmp_path / "data" / "01_raw" / "faxes"
    atomic = tmp_path / "data" / "02_triage" / "atomic_pages"
    ocr = tmp_path / "data" / "03_ocr"
    parsed = ocr / "parsed_text"
    structured = tmp_path / "data" / "04_structured"
    for directory in (faxes, atomic, ocr, parsed, structured):
        directory.mkdir(parents=True)

    (faxes / "packet_001_scanned.pdf").write_bytes(b"%PDF")
    (faxes / "packet_009_scanned.pdf").write_bytes(b"%PDF")
    (atomic / "packet_001_scanned_page_001.pdf").write_bytes(b"%PDF")
    (atomic / "packet_001_scanned_page_002.pdf").write_bytes(b"%PDF")
    (ocr / "packet_001_scanned_page_001.json").write_text("{}", encoding="utf-8")
    (parsed / "packet_001_scanned_page_001.txt").write_text("note", encoding="utf-8")
    (structured / "packet_001_scanned_page_001.json").write_text(
        json.dumps({"patient_name": "Ada"}), encoding="utf-8"
    )
    (structured / "packet_001_scanned_page_002.error.json").write_text(
        json.dumps({"stem": "packet_001_scanned_page_002", "error_type": "schema"}),
        encoding="utf-8",
    )

    catalog = load_catalog(tmp_path)
    packets = {packet.stem: packet for packet in catalog.packets}

    assert packets["packet_009_scanned"].pages == ()
    packet = packets["packet_001_scanned"]
    assert [page.stem for page in packet.pages] == [
        "packet_001_scanned_page_001",
        "packet_001_scanned_page_002",
    ]

    ready = packet.pages[0]
    assert ready.packet_pdf == faxes / "packet_001_scanned.pdf"
    assert ready.atomic_pdf is not None
    assert ready.ocr_json is not None
    assert ready.parsed_text is not None
    assert ready.structured_json is not None
    assert ready.error_json is None

    waiting = packet.pages[1]
    assert waiting.page_number == 2
    assert waiting.ocr_json is None
    assert waiting.structured_json is None
    assert waiting.error_json is not None
    assert waiting.error_json.name == "packet_001_scanned_page_002.error.json"
