"""FHIR R4 preview. A fact is included only after acceptance, and a code when one is required."""

import uuid
from datetime import datetime, timezone

from .facts import Fact
from .provenance import ProvenanceLink
from .review import ReviewEntry, effective_value

_NAMESPACE = uuid.UUID("6f1d8e2a-7c4b-4a1e-9d3f-8b2c5e6a7d10")
_ACCEPTED = {"accepted", "corrected"}
_CLINICAL_STATUS = {
    "active": "active",
    "resolved": "resolved",
    "historical": "inactive",
    "inactive": "inactive",
}
_GENDERS = {"male", "female", "other", "unknown"}


def build_bundle(
    *,
    stem: str,
    source_file: str | None,
    page_number: int | None,
    extraction: dict | None,
    facts: list[Fact],
    reviews: dict[str, ReviewEntry],
    links: list[ProvenanceLink],
) -> dict:
    """Build an in-memory collection bundle. Nothing here is posted to an EHR."""
    by_field = {link.field_path: link for link in links}
    included = [fact for fact in facts if _ready(fact, reviews.get(fact.field_path))]
    patient_fact = next((fact for fact in included if fact.field_path == "patient_name"), None)
    other_facts = [fact for fact in included if fact.field_path != "patient_name"]

    resources: list[dict] = []
    provenances: list[dict] = []
    patient_id = _stable_id(stem, "patient")
    need_patient = patient_fact is not None or bool(other_facts)
    if need_patient:
        patient = _patient(patient_id, patient_fact, reviews.get("patient_name") if patient_fact else None, extraction)
        resources.append(patient)
        if patient_fact is not None:
            provenance = _provenance(
                stem,
                patient_fact,
                patient_id,
                reviews[patient_fact.field_path],
                by_field.get(patient_fact.field_path),
                source_file,
                page_number,
            )
            if provenance is not None:
                provenances.append(provenance)

    for fact in other_facts:
        entry = reviews[fact.field_path]
        resource_id = _stable_id(stem, fact.field_path)
        if fact.kind == "Condition":
            resources.append(_condition(resource_id, patient_id, fact, entry))
        elif fact.kind == "Medication":
            resources.append(_medication(resource_id, patient_id, fact, entry))
        elif fact.kind == "Observation":
            resources.append(_observation(resource_id, patient_id, fact, entry))
        else:
            continue
        provenance = _provenance(
            stem, fact, resource_id, entry, by_field.get(fact.field_path), source_file, page_number
        )
        if provenance is not None:
            provenances.append(provenance)

    resources.extend(provenances)
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entry": [{"fullUrl": f"urn:uuid:{resource['id']}", "resource": resource} for resource in resources],
    }


def _ready(fact: Fact, entry: ReviewEntry | None) -> bool:
    if entry is None or entry.status not in _ACCEPTED:
        return False
    if fact.requires_code and not (entry.code and entry.code_system):
        return False
    return True


def _patient(patient_id: str, fact: Fact | None, entry: ReviewEntry | None, extraction: dict | None) -> dict:
    resource: dict = {"resourceType": "Patient", "id": patient_id}
    if fact is not None and entry is not None:
        resource["name"] = [{"text": effective_value(fact.value, entry)}]
        gender = ""
        if isinstance(extraction, dict) and isinstance(extraction.get("gender"), str):
            gender = extraction["gender"].strip().casefold()
        if gender in _GENDERS:
            resource["gender"] = gender
    return resource


def _condition(resource_id: str, patient_id: str, fact: Fact, entry: ReviewEntry) -> dict:
    text = effective_value(fact.value, entry)
    resource: dict = {
        "resourceType": "Condition",
        "id": resource_id,
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": _codeable(entry, text),
    }
    clinical = _CLINICAL_STATUS.get((fact.clinical_status or "").casefold())
    if clinical:
        resource["clinicalStatus"] = {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": clinical,
                }
            ]
        }
    return resource


def _observation(resource_id: str, patient_id: str, fact: Fact, entry: ReviewEntry) -> dict:
    text = effective_value(fact.value, entry)
    resource: dict = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "code": _codeable(entry, text),
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    quantity = _quantity(fact.result, fact.units)
    if quantity is not None:
        resource["valueQuantity"] = quantity
    elif fact.result:
        resource["valueString"] = fact.result
    interpretation = _interpretation(fact.flag)
    if interpretation is not None:
        resource["interpretation"] = [interpretation]
    return resource


_INTERPRETATION = {
    "high": ("H", "High"),
    "h": ("H", "High"),
    "low": ("L", "Low"),
    "l": ("L", "Low"),
    "abnormal": ("A", "Abnormal"),
}


def _quantity(result: str | None, units: str | None) -> dict | None:
    if not result:
        return None
    try:
        number = float(result)
    except ValueError:
        return None
    payload: dict = {"value": number}
    if units:
        payload["unit"] = units
    return payload


def _interpretation(flag: str | None) -> dict | None:
    if not flag:
        return None
    mapped = _INTERPRETATION.get(flag.casefold())
    if mapped is None:
        return {"text": flag}
    code, display = mapped
    return {
        "coding": [
            {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                "code": code,
                "display": display,
            }
        ],
        "text": display,
    }


def _medication(resource_id: str, patient_id: str, fact: Fact, entry: ReviewEntry) -> dict:
    text = effective_value(fact.value, entry)
    resource: dict = {
        "resourceType": "MedicationStatement",
        "id": resource_id,
        "status": "unknown",
        "subject": {"reference": f"Patient/{patient_id}"},
        "medicationCodeableConcept": _codeable(entry, text),
    }
    if fact.dosage:
        resource["dosage"] = [{"text": fact.dosage}]
    return resource


def _codeable(entry: ReviewEntry, text: str) -> dict:
    concept: dict = {"text": text}
    if entry.code and entry.code_system:
        coding = {"system": entry.code_system, "code": entry.code}
        if entry.display:
            coding["display"] = entry.display
        concept["coding"] = [coding]
    return concept


def _provenance(
    stem: str,
    fact: Fact,
    target_id: str,
    entry: ReviewEntry,
    link: ProvenanceLink | None,
    source_file: str | None,
    page_number: int | None,
) -> dict | None:
    if link is None or not link.resolved or link.block_index is None:
        return None
    file_name = link.source_file or source_file
    page = link.page_number if link.page_number is not None else page_number
    if not file_name or page is None:
        return None
    resource_type = _resource_type(fact)
    what: dict = {
        "identifier": {
            "system": "urn:ehr-migration-engine:source-span",
            "value": f"{file_name}#page={page}&block={link.block_index}",
        }
    }
    if link.block_text:
        what["display"] = link.block_text[:240]
    return {
        "resourceType": "Provenance",
        "id": _stable_id(stem, fact.field_path, "provenance"),
        "target": [{"reference": f"{resource_type}/{target_id}"}],
        "recorded": entry.timestamp,
        "agent": [{"who": {"display": "migration workbench"}}],
        "entity": [{"role": "source", "what": what}],
    }


def _resource_type(fact: Fact) -> str:
    if fact.kind == "Condition":
        return "Condition"
    if fact.kind == "Medication":
        return "MedicationStatement"
    if fact.kind == "Observation":
        return "Observation"
    return "Patient"


def _stable_id(*parts: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, "|".join(parts)))
