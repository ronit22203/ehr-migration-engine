import json
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
NORMALIZED_DIR = ROOT / "data" / "04_normalized"
FHIR_DIR = ROOT / "data" / "05_fhir"

def create_reference(resource_type: str, resource_id: str) -> dict:
    return {"reference": f"urn:uuid:{resource_id}"}

def build_fhir_bundle(data: dict) -> dict:
    patient_id = str(uuid.uuid4())
    entries = []

    # 1. Patient Resource
    patient_resource = {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"text": data.get("patient_name") or "Unknown Patient"}],
        "gender": str(data.get("gender", "unknown")).lower() if data.get("gender") else "unknown"
    }
    entries.append({"fullUrl": f"urn:uuid:{patient_id}", "resource": patient_resource})

    # 2. Condition Resources
    for cond in data.get("conditions", []):
        cond_id = str(uuid.uuid4())
        coding = cond.get("coding", {})
        condition_resource = {
            "resourceType": "Condition",
            "id": cond_id,
            "subject": create_reference("Patient", patient_id),
            "clinicalStatus": {
                "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
            },
            "code": {
                "coding": [{
                    "system": coding.get("system", "http://snomed.info/sct"),
                    "code": coding.get("code", "UNKNOWN"),
                    "display": coding.get("display", cond.get("diagnosis", ""))
                }],
                "text": cond.get("diagnosis", "")
            }
        }
        entries.append({"fullUrl": f"urn:uuid:{cond_id}", "resource": condition_resource})

    # 3. Observation Resources (Labs)
    for obs in data.get("observations", []):
        obs_id = str(uuid.uuid4())
        coding = obs.get("coding", {})
        
        # Try to parse the numeric value for valueQuantity
        val_str = obs.get("value", "")
        try:
            val_num = float(val_str)
        except ValueError:
            val_num = None

        observation_resource = {
            "resourceType": "Observation",
            "id": obs_id,
            "status": "final",
            "subject": create_reference("Patient", patient_id),
            "code": {
                "coding": [{
                    "system": coding.get("system", "http://loinc.org"),
                    "code": coding.get("code", "UNKNOWN"),
                    "display": coding.get("display", obs.get("test_name", ""))
                }],
                "text": obs.get("test_name", "")
            }
        }
        
        if val_num is not None:
            observation_resource["valueQuantity"] = {
                "value": val_num,
                "unit": obs.get("units", ""),
                "system": "http://unitsofmeasure.org",
                "code": obs.get("units", "")
            }
        else:
            observation_resource["valueString"] = val_str

        entries.append({"fullUrl": f"urn:uuid:{obs_id}", "resource": observation_resource})

    # 4. Medication Resources
    for med in data.get("medications", []):
        med_id = str(uuid.uuid4())
        coding = med.get("coding", {})
        medication_resource = {
            "resourceType": "MedicationStatement",
            "id": med_id,
            "status": "active",
            "subject": create_reference("Patient", patient_id),
            "medicationCodeableConcept": {
                "coding": [{
                    "system": coding.get("system", "http://www.nlm.nih.gov/research/umls/rxnorm"),
                    "code": coding.get("code", "UNKNOWN"),
                    "display": coding.get("display", med.get("name", ""))
                }],
                "text": med.get("name", "")
            },
            "dosage": [{"text": med.get("dosage", "")}] if med.get("dosage") else []
        }
        entries.append({"fullUrl": f"urn:uuid:{med_id}", "resource": medication_resource})

    # Wrap in a FHIR Transaction Bundle
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": entries
    }

def run_serialization():
    FHIR_DIR.mkdir(parents=True, exist_ok=True)
    json_files = sorted(NORMALIZED_DIR.glob("*.json"))

    print(f"[*] Serializing {len(json_files)} normalized documents to FHIR Bundles...")
    success_count = 0

    for json_path in json_files:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            fhir_bundle = build_fhir_bundle(data)

            out_path = FHIR_DIR / json_path.name
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(fhir_bundle, f, indent=2)
            
            success_count += 1
        except Exception as e:
            print(f"  [X] Failed to serialize {json_path.name}: {e}")

    print(f"[*] Serialization complete. Wrote {success_count} FHIR Bundles to {FHIR_DIR}")

if __name__ == "__main__":
    run_serialization()
