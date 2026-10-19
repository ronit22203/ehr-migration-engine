import json
from pydantic import ValidationError
from .schemas import ClinicalNoteExtraction

def validate_extraction(raw_json_str: str) -> tuple[bool, ClinicalNoteExtraction | str]:
    """
    Attempts to parse the LLM output into the strict Pydantic schema.
    Returns (True, parsed_object) if valid.
    Returns (False, error_message) if invalid, triggering the engine to loop and retry.
    """
    try:
        # Strip markdown formatting if the model wraps the response
        clean_str = raw_json_str.strip()
        if clean_str.startswith("```json"):
            clean_str = clean_str[7:-3].strip()
        elif clean_str.startswith("```"):
            clean_str = clean_str[3:-3].strip()
            
        data = json.loads(clean_str)
        validated = ClinicalNoteExtraction(**data)
        return True, validated
        
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON format. Error: {str(e)}. Output ONLY valid JSON without conversational text."
    except ValidationError as e:
        return False, f"Schema mismatch. Validation errors: {e.json()}. Fix the missing or malformed keys."

