from ehr_migration_engine.workbench.facts import facts_from_extraction
from ehr_migration_engine.workbench.fhir_preview import build_bundle
from ehr_migration_engine.workbench.provenance import ProvenanceLink
from ehr_migration_engine.workbench.review import ReviewEntry

STEM = "packet_001_scanned_page_001"
SOURCE = "packet_001_scanned_page_001.pdf"
EXTRACTION = {
    "patient_name": "Ada Lovelace",
    "age": 36,
    "gender": "female",
    "conditions": [{"diagnosis": "Hypertension", "status": "active"}],
    "medications": [{"name": "Lisinopril", "dosage": "10 mg"}],
}


def _entry(**overrides: object) -> ReviewEntry:
    payload = {
        "stem": STEM,
        "field_path": "conditions[0].diagnosis",
        "status": "accepted",
        "original_value": "Hypertension",
        "revised_value": None,
        "code_system": None,
        "code": None,
        "display": None,
        "reason": None,
        "timestamp": "2026-10-20T00:00:00+00:00",
    }
    payload.update(overrides)
    return ReviewEntry(**payload)  # type: ignore[arg-type]


def _links() -> list[ProvenanceLink]:
    return [
        ProvenanceLink(
            field_path="conditions[0].diagnosis",
            value="Hypertension",
            resolved=True,
            source_file=SOURCE,
            page_number=1,
            block_index=2,
            reading_order=7,
            block_text="Allergy / Immunology -- Chronic Sinusitis",
            bbox=(1.0, 2.0, 3.0, 4.0),
            confidence=0.96,
            label="ListGroup",
        ),
        ProvenanceLink(
            field_path="medications[0].name",
            value="Lisinopril",
            resolved=True,
            source_file=SOURCE,
            page_number=1,
            block_index=4,
            reading_order=8,
            block_text="Lisinopril 10 mg",
            bbox=(5.0, 6.0, 7.0, 8.0),
            confidence=None,
            label="Text",
        ),
        ProvenanceLink(
            field_path="patient_name",
            value="Ada Lovelace",
            resolved=False,
            source_file=SOURCE,
            page_number=1,
            block_index=None,
            reading_order=None,
            block_text=None,
            bbox=None,
            confidence=None,
            label=None,
        ),
    ]


def _bundle(reviews: dict[str, ReviewEntry]) -> dict:
    return build_bundle(
        stem=STEM,
        source_file=SOURCE,
        page_number=1,
        extraction=EXTRACTION,
        facts=facts_from_extraction(EXTRACTION),
        reviews=reviews,
        links=_links(),
    )


def _types(bundle: dict) -> list[str]:
    return [item["resource"]["resourceType"] for item in bundle["entry"]]


def test_omits_a_fact_until_it_is_accepted_and_coded() -> None:
    assert _types(_bundle({})) == []

    uncoded = _bundle({"conditions[0].diagnosis": _entry()})
    assert "Condition" not in _types(uncoded)
    assert "Provenance" not in _types(uncoded)

    rejected = _bundle(
        {
            "conditions[0].diagnosis": _entry(
                status="rejected",
                reason="Not on the page",
                code_system="http://snomed.info/sct",
                code="38341003",
                display="Hypertensive disorder",
            )
        }
    )
    assert "Condition" not in _types(rejected)

    bundle = _bundle(
        {
            "conditions[0].diagnosis": _entry(
                code_system="http://snomed.info/sct",
                code="38341003",
                display="Hypertensive disorder",
            )
        }
    )
    resources = {item["resource"]["resourceType"]: item["resource"] for item in bundle["entry"]}
    condition = next(
        item["resource"] for item in bundle["entry"] if item["resource"]["resourceType"] == "Condition"
    )
    provenance = next(
        item["resource"] for item in bundle["entry"] if item["resource"]["resourceType"] == "Provenance"
    )

    assert "MedicationStatement" not in resources
    assert "name" not in resources["Patient"]
    assert condition["code"]["coding"][0]["code"] == "38341003"
    assert condition["clinicalStatus"]["coding"][0]["code"] == "active"
    assert provenance["target"][0]["reference"] == f"Condition/{condition['id']}"
    identifier = provenance["entity"][0]["what"]["identifier"]["value"]
    assert SOURCE in identifier
    assert "page=1" in identifier
    assert "block=2" in identifier


def test_corrected_patient_name_and_coded_medication_are_delivered() -> None:
    bundle = _bundle(
        {
            "patient_name": _entry(
                field_path="patient_name",
                status="corrected",
                original_value="Ada Lovelace",
                revised_value="Ada L.",
                reason="Shortened for the preview",
            ),
            "medications[0].name": _entry(
                field_path="medications[0].name",
                original_value="Lisinopril",
                code_system="http://www.nlm.nih.gov/research/umls/rxnorm",
                code="29046",
                display="Lisinopril",
            ),
        }
    )
    patient = next(item["resource"] for item in bundle["entry"] if item["resource"]["resourceType"] == "Patient")
    medication = next(
        item["resource"]
        for item in bundle["entry"]
        if item["resource"]["resourceType"] == "MedicationStatement"
    )
    provenance = next(
        item["resource"]
        for item in bundle["entry"]
        if item["resource"]["resourceType"] == "Provenance"
        and item["resource"]["target"][0]["reference"].startswith("MedicationStatement/")
    )

    assert patient["name"][0]["text"] == "Ada L."
    assert patient["gender"] == "female"
    assert medication["medicationCodeableConcept"]["coding"][0]["code"] == "29046"
    assert medication["dosage"][0]["text"] == "10 mg"
    assert "page=1" in provenance["entity"][0]["what"]["identifier"]["value"]
    assert "block=4" in provenance["entity"][0]["what"]["identifier"]["value"]
    assert "Condition" not in _types(bundle)


def test_accepted_lab_row_is_an_observation() -> None:
    extraction = {
        "patient_name": "Lyubochka Svetka",
        "conditions": [{"diagnosis": "High Triglycerides", "status": "High"}],
        "medications": [],
        "observations": [
            {"test_name": "Triglyceride", "value": "168.0", "units": "mg/dL", "flag": "High"},
        ],
    }
    reviews = {
        "observations[0].test_name": _entry(
            field_path="observations[0].test_name",
            original_value="Triglyceride",
            code_system="http://loinc.org",
            code="2571-8",
            display="Triglyceride [Mass/volume] in Serum or Plasma",
        )
    }
    links = [
        ProvenanceLink(
            field_path="observations[0].test_name",
            value="Triglyceride",
            resolved=True,
            source_file=SOURCE,
            page_number=3,
            block_index=5,
            reading_order=4,
            block_text="Triglyceride H 168.0 mg/dL",
            bbox=(1.0, 2.0, 3.0, 4.0),
            confidence=0.9,
            label="Table",
        )
    ]
    bundle = build_bundle(
        stem=STEM,
        source_file=SOURCE,
        page_number=3,
        extraction=extraction,
        facts=facts_from_extraction(extraction),
        reviews=reviews,
        links=links,
    )
    observation = next(
        item["resource"] for item in bundle["entry"] if item["resource"]["resourceType"] == "Observation"
    )
    provenance = next(
        item["resource"] for item in bundle["entry"] if item["resource"]["resourceType"] == "Provenance"
    )

    assert observation["code"]["coding"][0]["code"] == "2571-8"
    assert observation["valueQuantity"] == {"value": 168.0, "unit": "mg/dL"}
    assert observation["interpretation"][0]["coding"][0]["code"] == "H"
    assert provenance["target"][0]["reference"] == f"Observation/{observation['id']}"
    assert "Condition" not in _types(bundle)
