import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ehr_migration_engine.workbench import api as workbench_api


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    faxes = tmp_path / "data" / "01_raw" / "faxes"
    atomic = tmp_path / "data" / "02_triage" / "atomic_pages"
    ocr = tmp_path / "data" / "03_ocr"
    structured = tmp_path / "data" / "04_structured"
    fhir = tmp_path / "data" / "05_fhir"
    for directory in (faxes, atomic, ocr, structured, fhir):
        directory.mkdir(parents=True)

    (faxes / "packet_001_scanned.pdf").write_bytes(b"%PDF")
    (atomic / "packet_001_scanned_page_001.pdf").write_bytes(b"%PDF")
    (ocr / "packet_001_scanned_page_001.json").write_text(
        json.dumps({"source": "packet_001_scanned_page_001.pdf", "blocks": []}),
        encoding="utf-8",
    )
    (structured / "packet_001_scanned_page_001.json").write_text(
        json.dumps(
            {
                "patient_name": "Ada Lovelace",
                "conditions": [{"diagnosis": "Hypertension", "status": "active"}],
                "medications": [],
                "observations": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("EHR_MIGRATION_ROOT", str(tmp_path))
    return TestClient(workbench_api.app)


def test_batch_lists_pages_and_counts(client: TestClient) -> None:
    payload = client.get("/api/batch").json()

    assert payload["batch_id"] == "local-faxes"
    assert payload["counts"]["pages"] == 1
    assert payload["counts"]["structured"] == 1
    assert payload["packets"][0]["pages"][0]["stem"] == "packet_001_scanned_page_001"


def test_review_accepts_a_coded_condition(client: TestClient, tmp_path: Path) -> None:
    detail = client.get("/api/pages/packet_001_scanned_page_001").json()
    assert detail["facts"][1]["field_path"] == "conditions[0].diagnosis"

    response = client.post(
        "/api/pages/packet_001_scanned_page_001/review",
        json={
            "field_path": "conditions[0].diagnosis",
            "status": "accepted",
            "code_system": "http://snomed.info/sct",
            "code": "38341003",
            "display": "Hypertensive disorder",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["entry"]["code"] == "38341003"

    ledger = tmp_path / "data" / "06_review" / "ledger.jsonl"
    assert ledger.is_file()
    line = json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
    assert line["status"] == "accepted"
    assert line["field_path"] == "conditions[0].diagnosis"


def test_missing_fhir_bundle_is_reported(client: TestClient) -> None:
    payload = client.get("/api/pages/packet_001_scanned_page_001/fhir").json()

    assert payload["available"] is False
    assert payload["bundle"] is None


def test_unknown_page_returns_404(client: TestClient) -> None:
    response = client.get("/api/pages/missing_page")
    assert response.status_code == 404
