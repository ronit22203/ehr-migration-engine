"""Download MTSamples clinical notes into data/01_raw/mtsamples."""

from pathlib import Path

from datasets import load_dataset

# Resolve from this file so notes land in the repo data/ tree
# even when the script is started from another directory.
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "01_raw" / "mtsamples"
# Public copy of the MTSamples transcription table (specialty, sample name, transcription).
DATASET_ID = "harishnair04/mtsamples"


def _safe_specialty(value: object) -> str:
    specialty = str(value or "general").strip() or "general"
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in specialty)
    return "_".join(part for part in cleaned.split("_") if part) or "general"


def fetch_medical_transcriptions() -> None:
    print("[*] Downloading MTSamples dataset from Hugging Face...")
    dataset = load_dataset(DATASET_ID, split="train")
    df = dataset.to_pandas()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RAW_DIR / "clinical_notes_full.csv"
    df.to_csv(csv_path, index=False)
    print(f"[*] Saved {len(df)} clinical notes to {csv_path}")

    txt_dir = RAW_DIR / "text_files"
    txt_dir.mkdir(parents=True, exist_ok=True)

    for i, row in df.head(20).iterrows():
        subject = _safe_specialty(row.get("medical_specialty"))
        file_path = txt_dir / f"note_{i:03d}_{subject}.txt"
        transcription = row.get("transcription") or ""
        file_path.write_text(
            f"Specialty: {row.get('medical_specialty')}\n"
            f"Sample Name: {row.get('sample_name')}\n\n"
            f"{transcription}",
            encoding="utf-8",
        )

    print(f"[*] Saved 20 individual .txt clinical notes to {txt_dir}")


if __name__ == "__main__":
    fetch_medical_transcriptions()
