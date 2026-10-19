from pydantic import BaseModel, Field

class Medication(BaseModel):
    name: str
    dosage: str | None = None

class Condition(BaseModel):
    diagnosis: str
    status: str | None = Field(description="Active, historical, or resolved")

class ClinicalNoteExtraction(BaseModel):
    patient_name: str | None = None
    age: int | None = None
    gender: str | None = None
    conditions: list[Condition] = []
    medications: list[Medication] = []

