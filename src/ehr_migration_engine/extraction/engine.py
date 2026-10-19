import json
from pathlib import Path
from openai import OpenAI
from .state_machine import validate_extraction

ROOT = Path(__file__).resolve().parents[3]
TEXT_DIR = ROOT / "data" / "03_ocr" / "parsed_text"
STRUCTURED_DIR = ROOT / "data" / "04_structured"

# Ollama's local OpenAI-compatible endpoint
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
MODEL = "medgemma:4b"
MAX_RETRIES = 3

SYSTEM_PROMPT = """You are a highly precise clinical data extraction system.
Extract the patient demographics, conditions, and medications from the clinical note.
You MUST output strictly valid JSON conforming to this schema:
{
  "patient_name": "string or null",
  "age": "integer or null",
  "gender": "string or null",
  "conditions": [{"diagnosis": "string", "status": "string"}],
  "medications": [{"name": "string", "dosage": "string"}]
}
Do not output any markdown formatting, conversational text, or explanations. Return ONLY the JSON object.
"""

def extract_clinical_data():
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    txt_files = sorted(TEXT_DIR.glob("*.txt"))
    
    if not txt_files:
        print(f"[!] No parsed text files found in {TEXT_DIR}")
        return

    print(f"[*] Starting deterministic extraction on {len(txt_files)} notes using {MODEL}...")
    
    for txt_path in txt_files:
        out_path = STRUCTURED_DIR / f"{txt_path.stem}.json"
        if out_path.exists():
            continue
            
        with open(txt_path, "r", encoding="utf-8") as f:
            clinical_text = f.read()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": clinical_text}
        ]
        
        success = False
        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    temperature=0.0  # Zero creativity, strict adherence
                )
                raw_output = response.choices[0].message.content
                
                is_valid, result = validate_extraction(raw_output)
                
                if is_valid:
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(result.model_dump(), f, indent=2)
                    print(f"  -> Extracted: {txt_path.name}")
                    success = True
                    break
                else:
                    print(f"  [!] Schema mismatch on {txt_path.name} (Attempt {attempt+1}). Looping DFA...")
                    messages.append({"role": "assistant", "content": raw_output})
                    messages.append({"role": "user", "content": result}) 
                    
            except Exception as e:
                print(f"  [X] API Error on {txt_path.name}: {e}")
                break
        
        if not success:
            print(f"  [X] Failed to extract {txt_path.name} after {MAX_RETRIES} attempts.")

if __name__ == "__main__":
    extract_clinical_data()

