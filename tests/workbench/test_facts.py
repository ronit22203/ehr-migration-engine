from ehr_migration_engine.workbench.facts import facts_from_extraction


def test_lipid_rows_are_observations_and_invented_diagnoses_stay_conditions() -> None:
    extraction = {
        "patient_name": "Lyubochka Svetka",
        "conditions": [
            {"diagnosis": "High Cholesterol", "status": "High"},
            {"diagnosis": "High Triglycerides", "status": "High"},
        ],
        "medications": [],
        "observations": [
            {"test_name": "Cholesterol", "value": "189.0", "units": "mg/dL", "flag": "High"},
            {"test_name": "Triglyceride", "value": "168.0", "units": "mg/dL", "flag": "High"},
            {"test_name": "CHOL/HDL Ratio", "value": "3.1", "units": None, "flag": "High"},
        ],
    }

    facts = facts_from_extraction(extraction)
    triglyceride = next(fact for fact in facts if fact.value == "Triglyceride")

    assert [fact.kind for fact in facts] == ["Patient", "Condition", "Condition", "Observation", "Observation", "Observation"]
    assert triglyceride.field_path == "observations[1].test_name"
    assert triglyceride.result == "168.0"
    assert triglyceride.units == "mg/dL"
    assert triglyceride.flag == "High"
    assert triglyceride.requires_code is True
    ratio = facts[-1]
    assert ratio.value == "CHOL/HDL Ratio"
    assert ratio.units is None
