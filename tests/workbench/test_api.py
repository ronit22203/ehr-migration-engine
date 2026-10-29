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


def test_upload_and_delete_fax(client: TestClient, tmp_path: Path) -> None:
    prior = tmp_path / "data" / "01_raw" / "faxes" / "packet_001_scanned.pdf"
    prior_atomic = tmp_path / "data" / "02_triage" / "atomic_pages" / "packet_001_scanned_page_001.pdf"
    assert prior.is_file()
    assert prior_atomic.is_file()

    response = client.post(
        "/api/faxes",
        files={"file": ("Clinic Note.pdf", b"%PDF-1.4 demo", "application/pdf")},
    )
    assert response.status_code == 200
    fax = response.json()["fax"]
    assert fax["filename"] == "Clinic-Note.pdf"
    assert fax["cleared"] >= 1
    assert (tmp_path / "data" / "01_raw" / "faxes" / "Clinic-Note.pdf").is_file()
    # Upload replaces the drop: prior packets and their derived pages go away.
    assert not prior.is_file()
    assert not prior_atomic.is_file()

    listed = client.get("/api/faxes").json()["faxes"]
    assert [item["stem"] for item in listed] == ["Clinic-Note"]

    deleted = client.delete("/api/faxes/Clinic-Note")
    assert deleted.status_code == 200
    assert deleted.json()["count"] >= 1
    assert not (tmp_path / "data" / "01_raw" / "faxes" / "Clinic-Note.pdf").is_file()


def test_delete_packet_removes_derived_pages(client: TestClient, tmp_path: Path) -> None:
    atomic = tmp_path / "data" / "02_triage" / "atomic_pages" / "packet_001_scanned_page_001.pdf"
    assert atomic.is_file()

    response = client.delete("/api/faxes/packet_001_scanned")
    assert response.status_code == 200
    assert response.json()["count"] >= 2
    assert not atomic.is_file()
    assert not (tmp_path / "data" / "01_raw" / "faxes" / "packet_001_scanned.pdf").is_file()


def test_pipeline_actions_are_listed(client: TestClient) -> None:
    payload = client.get("/api/pipeline/actions").json()
    ids = {action["id"] for action in payload["actions"]}
    assert {"data-run-raw", "ocr", "extract", "normalize", "fhir", "clean"}.issubset(ids)


def test_pipeline_rejects_unknown_action(client: TestClient) -> None:
    response = client.post("/api/pipeline/run", json={"action": "not-a-target"})
    assert response.status_code == 400


def test_pipeline_kill_with_no_job_returns_409(client: TestClient) -> None:
    response = client.post("/api/pipeline/kill")
    assert response.status_code == 409
