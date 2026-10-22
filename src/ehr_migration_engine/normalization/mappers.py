"""
Terminology mapper for clinical entities.
Maps extracted plain-text strings to standardized codes:
- Conditions: SNOMED CT / ICD-10
- Medications: RxNorm
- Observations (Labs): LOINC
"""

from dataclasses import dataclass
from thefuzz import process, fuzz


@dataclass
class Coding:
    system: str
    code: str
    display: str


# Core reference lookup tables (expandable with UMLS / NLM releases)
SNOMED_ICD_LEXICON = {
    "hypercholesterolemia": Coding("http://snomed.info/sct", "13644009", "Hypercholesterolemia"),
    "high cholesterol": Coding("http://snomed.info/sct", "13644009", "Hypercholesterolemia"),
    "hypertriglyceridemia": Coding("http://snomed.info/sct", "302870006", "Hypertriglyceridemia"),
    "high triglycerides": Coding("http://snomed.info/sct", "302870006", "Hypertriglyceridemia"),
    "essential hypertension": Coding("http://snomed.info/sct", "59621000", "Essential hypertension"),
    "high blood pressure": Coding("http://snomed.info/sct", "59621000", "Essential hypertension"),
    "hypertension": Coding("http://snomed.info/sct", "59621000", "Essential hypertension"),
    "type 2 diabetes mellitus": Coding("http://snomed.info/sct", "44054006", "Type 2 diabetes mellitus"),
    "diabetes": Coding("http://snomed.info/sct", "73211009", "Diabetes mellitus"),
    "obesity": Coding("http://snomed.info/sct", "414915002", "Obese"),
    "asthma": Coding("http://snomed.info/sct", "195967001", "Asthma"),
}

RXNORM_LEXICON = {
    "atorvastatin": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "83367", "Atorvastatin"),
    "lipitor": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "153165", "Lipitor"),
    "metformin": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "6809", "Metformin"),
    "lisinopril": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "29046", "Lisinopril"),
    "crestor": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "352377", "Crestor"),
    "diovan": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "214199", "Diovan"),
    "tricor": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "152839", "Tricor"),
    "tylenol": Coding("http://www.nlm.nih.gov/research/umls/rxnorm", "202433", "Tylenol"),
}

LOINC_LEXICON = {
    "cholesterol": Coding("http://loinc.org", "2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
    "total cholesterol": Coding("http://loinc.org", "2093-3", "Cholesterol [Mass/volume] in Serum or Plasma"),
    "triglyceride": Coding("http://loinc.org", "2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
    "triglycerides": Coding("http://loinc.org", "2571-8", "Triglyceride [Mass/volume] in Serum or Plasma"),
    "hdl cholesterol": Coding("http://loinc.org", "2085-9", "HDL Cholesterol [Mass/volume] in Serum or Plasma"),
    "direct ldl": Coding("http://loinc.org", "18262-6", "LDL Cholesterol [Mass/volume] in Serum or Plasma by Direct assay"),
    "ldl cholesterol": Coding("http://loinc.org", "18262-6", "LDL Cholesterol [Mass/volume] in Serum or Plasma by Direct assay"),
    "vldl": Coding("http://loinc.org", "13457-7", "Cholesterol in VLDL [Mass/volume] in Serum or Plasma"),
    "chol/hdl ratio": Coding("http://loinc.org", "9830-1", "Cholesterol.total/Cholesterol in HDL in Serum or Plasma"),
    "glucose": Coding("http://loinc.org", "2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
    "hemoglobin": Coding("http://loinc.org", "718-7", "Hemoglobin [Mass/volume] in Blood"),
    "wbc": Coding("http://loinc.org", "6690-2", "Leukocytes [#/volume] in Blood by Automated count"),
    "creatinine": Coding("http://loinc.org", "2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
    "bun": Coding("http://loinc.org", "3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
    "hemoglobin a1c": Coding("http://loinc.org", "4548-4", "Hemoglobin A1c/Hemoglobin.total in Blood"),
    "tsh": Coding("http://loinc.org", "3016-3", "Thyrotropin [Units/volume] in Serum or Plasma"),
}


def normalize_term(term: str, lexicon: dict[str, Coding], cutoff: int = 75) -> Coding:
    """Matches a term to an ontology using exact match with token-sort fuzzy fallback."""
    if not term:
        return Coding("http://terminology.hl7.org/CodeSystem/data-absent-reason", "unknown", "Unknown")

    cleaned = term.lower().strip()

    if cleaned in lexicon:
        return lexicon[cleaned]

    best_match, score = process.extractOne(cleaned, list(lexicon.keys()), scorer=fuzz.token_sort_ratio)
    if score >= cutoff:
        return lexicon[best_match]

    # Unmapped fallback
    return Coding("http://local-terms.internal", "LOCAL-UNMAPPED", term)


def normalize_condition(diagnosis: str) -> Coding:
    return normalize_term(diagnosis, SNOMED_ICD_LEXICON)


def normalize_medication(name: str) -> Coding:
    return normalize_term(name, RXNORM_LEXICON)


def normalize_observation(test_name: str) -> Coding:
    return normalize_term(test_name, LOINC_LEXICON)
