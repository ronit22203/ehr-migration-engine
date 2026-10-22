from ehr_migration_engine.normalization.mappers import (
    normalize_condition,
    normalize_medication,
    normalize_observation,
)


def test_exact_terms_map_to_standard_codes() -> None:
    cholesterol = normalize_condition("High Cholesterol")
    tylenol = normalize_medication("Tylenol")
    triglyceride = normalize_observation("Triglyceride")

    assert cholesterol.system == "http://snomed.info/sct"
    assert cholesterol.code == "13644009"
    assert cholesterol.display == "Hypercholesterolemia"

    assert tylenol.system == "http://www.nlm.nih.gov/research/umls/rxnorm"
    assert tylenol.code == "202433"
    assert tylenol.display == "Tylenol"

    assert triglyceride.system == "http://loinc.org"
    assert triglyceride.code == "2571-8"
    assert triglyceride.display == "Triglyceride [Mass/volume] in Serum or Plasma"


def test_fuzzy_typo_maps_above_the_cutoff() -> None:
    coding = normalize_condition("high cholestrol")

    assert coding.code == "13644009"
    assert coding.display == "Hypercholesterolemia"


def test_unmapped_term_keeps_the_original_text() -> None:
    coding = normalize_observation("not a real analyte xyz")

    assert coding.system == "http://local-terms.internal"
    assert coding.code == "LOCAL-UNMAPPED"
    assert coding.display == "not a real analyte xyz"
