"""Typed facts drawn from a ClinicalNoteExtraction document."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fact:
    field_path: str
    kind: str
    value: str
    requires_code: bool
    dosage: str | None = None
    clinical_status: str | None = None
    result: str | None = None
    units: str | None = None
    flag: str | None = None


def facts_from_extraction(extraction: dict | None) -> list[Fact]:
    """List reviewable facts. Schema-valid JSON can still contain nothing to code."""
    if not isinstance(extraction, dict):
        return []

    facts: list[Fact] = []
    patient_name = _text(extraction.get("patient_name"))
    if patient_name:
        facts.append(
            Fact(
                field_path="patient_name",
                kind="Patient",
                value=patient_name,
                requires_code=False,
            )
        )

    conditions = extraction.get("conditions")
    if isinstance(conditions, list):
        for index, item in enumerate(conditions):
            if not isinstance(item, dict):
                continue
            diagnosis = _text(item.get("diagnosis"))
            if not diagnosis:
                continue
            facts.append(
                Fact(
                    field_path=f"conditions[{index}].diagnosis",
                    kind="Condition",
                    value=diagnosis,
                    requires_code=True,
                    clinical_status=_text(item.get("status")),
                )
            )

    medications = extraction.get("medications")
    if isinstance(medications, list):
        for index, item in enumerate(medications):
            if not isinstance(item, dict):
                continue
            name = _text(item.get("name"))
            if not name:
                continue
            facts.append(
                Fact(
                    field_path=f"medications[{index}].name",
                    kind="Medication",
                    value=name,
                    requires_code=True,
                    dosage=_text(item.get("dosage")),
                )
            )

    observations = extraction.get("observations")
    if isinstance(observations, list):
        for index, item in enumerate(observations):
            if not isinstance(item, dict):
                continue
            test_name = _text(item.get("test_name"))
            if not test_name:
                continue
            facts.append(
                Fact(
                    field_path=f"observations[{index}].test_name",
                    kind="Observation",
                    value=test_name,
                    requires_code=True,
                    result=_text(item.get("value")),
                    units=_text(item.get("units")),
                    flag=_text(item.get("flag")),
                )
            )

    return facts


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
