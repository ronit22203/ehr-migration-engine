import json
import threading
import time
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from .failures import clear_extraction_error, write_extraction_error
from .state_machine import validate_extraction

ROOT = Path(__file__).resolve().parents[3]
TEXT_DIR = ROOT / "data" / "03_ocr" / "parsed_text"
STRUCTURED_DIR = ROOT / "data" / "04_structured"

# Ollama's local OpenAI-compatible endpoint.
# The SDK otherwise waits 10 minutes, which is what turned one slow page into a 500.
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama", timeout=120.0)
MODEL = "medgemma:4b"
MAX_RETRIES = 3
MAX_TOKENS = 768


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"{stamp} [*] {message}", flush=True)


class _WaitLog:
    """Print a line every few seconds while a completion call is blocking."""

    def __init__(self, message: str, interval: float = 15.0) -> None:
        self._message = message
        self._interval = interval
        self._stop = threading.Event()
        self._started = time.perf_counter()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> "_WaitLog":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=1)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            elapsed = time.perf_counter() - self._started
            _log(f"{self._message} ({elapsed:.0f}s elapsed, still waiting)")

SYSTEM_PROMPT = """You are a highly precise clinical data extraction system.
Extract the patient demographics, conditions, medications, and lab observations from the clinical note.
You MUST output strictly valid JSON conforming to this schema:
{
  "patient_name": "string or null",
  "age": "integer or null",
  "gender": "string or null",
  "conditions": [{"diagnosis": "string", "status": "string"}],
  "medications": [{"name": "string", "dosage": "string"}],
  "observations": [{"test_name": "string", "value": "string", "units": "string", "flag": "string"}]
}
CRITICAL INSTRUCTIONS:
1. Do NOT put lab results, vitals, or analytes into "conditions". They belong in "observations".
2. An H, L, High, or Low mark on a result row is the observation "flag". It is not a diagnosis and it is not a condition status.
3. Do not invent a condition from a flagged row. "H 168.0" beside Triglyceride is not "High Triglycerides".
4. Do not hallucinate flags for normal lab values. Leave "flag" null when the row has no H or L mark and the result sits inside the reference interval.
5. Do not output any markdown formatting, conversational text, or explanations. Return ONLY the JSON object.

EXAMPLE
A lipid-profile row is one observation. Copy this shape for every analyte row in the note. Do not copy these numbers unless that row is on the page.

Input row:
| Triglyceride | H 168.0 | mg/dL | Normal : <150 |

Output:
{"patient_name": null, "age": null, "gender": null, "conditions": [], "medications": [], "observations": [{"test_name": "Triglyceride", "value": "168.0", "units": "mg/dL", "flag": "High"}]}
"""

def extract_clinical_data():
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    txt_files = sorted(TEXT_DIR.glob("*.txt"))
    
    if not txt_files:
        print(f"[!] No parsed text files found in {TEXT_DIR}")
        return

    print(f"[*] Starting deterministic extraction on {len(txt_files)} notes using {MODEL}...", flush=True)
    
    for index, txt_path in enumerate(txt_files, start=1):
        out_path = STRUCTURED_DIR / f"{txt_path.stem}.json"
        if out_path.exists():
            _log(f"[{index}/{len(txt_files)}] skip {txt_path.name} (already extracted)")
            continue
            
        with open(txt_path, "r", encoding="utf-8") as f:
            clinical_text = f.read()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": clinical_text}
        ]
        
        success = False
        attempts_used = 0
        last_error_type = "schema"
        last_message = "Extraction did not produce a schema-valid record."
        for attempt in range(MAX_RETRIES):
            attempts_used = attempt + 1
            _log(
                f"[{index}/{len(txt_files)}] {txt_path.name} "
                f"attempt {attempt + 1}/{MAX_RETRIES} ({len(clinical_text)} chars)"
            )
            try:
                with _WaitLog(f"{txt_path.name}: Ollama is generating"):
                    response = client.chat.completions.create(
                        model=MODEL,
                        messages=messages,
                        temperature=0.0,
                        max_tokens=MAX_TOKENS,
                    )
                raw_output = response.choices[0].message.content
                
                is_valid, result = validate_extraction(raw_output)
                
                if is_valid:
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(result.model_dump(), f, indent=2)
                    clear_extraction_error(STRUCTURED_DIR, txt_path.stem)
                    _log(f"  extracted {txt_path.name}")
                    success = True
                    break
                else:
                    failure = str(result)
                    last_error_type = "invalid_json" if failure.startswith("Invalid JSON") else "schema"
                    last_message = failure
                    _log(f"  schema mismatch on {txt_path.name} (attempt {attempt + 1}). Retrying.")
                    messages.append({"role": "assistant", "content": raw_output})
                    messages.append({"role": "user", "content": result}) 
                    
            except Exception as e:
                last_error_type = "api"
                last_message = f"{type(e).__name__}: {e}"
                _log(f"  API error on {txt_path.name}: {e}")
                break
        
        if not success:
            write_extraction_error(
                STRUCTURED_DIR,
                txt_path.stem,
                attempts_used,
                last_error_type,
                last_message,
            )
            _log(f"  failed {txt_path.name} after {attempts_used} attempts. Continuing.")

if __name__ == "__main__":
    extract_clinical_data()

