import json
from pathlib import Path
from ehr_migration_engine.normalization.mappers import (
    normalize_condition,
    normalize_medication,
    normalize_observation,
)

ROOT = Path(__file__).resolve().parents[3]
STRUCTURED_DIR = ROOT / "data" / "04_structured"
NORMALIZED_DIR = ROOT / "data" / "04_normalized"


def run_normalization():
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    json_files = sorted(STRUCTURED_DIR.glob("*.json"))

    print(f"[*] Starting Semantic Normalization across {len(json_files)} extracted files...")
    success_count = 0

    for json_path in json_files:
        if json_path.name.endswith(".error.json"):
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Normalize conditions
        for cond in data.get("conditions", []):
            coding = normalize_condition(cond.get("diagnosis", ""))
            cond["coding"] = coding.__dict__

        # Normalize medications
        for med in data.get("medications", []):
            coding = normalize_medication(med.get("name", ""))
            med["coding"] = coding.__dict__

        # Normalize observations
        for obs in data.get("observations", []):
            coding = normalize_observation(obs.get("test_name", ""))
            obs["coding"] = coding.__dict__

        out_path = NORMALIZED_DIR / json_path.name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        success_count += 1

    print(f"[*] Normalization complete. Enriched {success_count} documents in {NORMALIZED_DIR}")


if __name__ == "__main__":
    run_normalization()
