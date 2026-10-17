"""Download MTSamples clinical notes into data/01_raw/mtsamples."""

from pathlib import Path

import pandas as pd
from datasets import load_dataset

# Resolve from this file so notes land in the repo data/ tree
# even when the script is started from another directory.
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "01_raw" / "mtsamples"
# Public copy of the MTSamples transcription table (specialty, sample name, transcription).
DATASET_ID = "harishnair04/mtsamples"

NOTE_COUNT = 24
MIN_CHARS = 4000


def _safe_specialty(value: object) -> str:
    specialty = str(value or "general").strip() or "general"
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in specialty)
    return "_".join(part for part in cleaned.split("_") if part) or "general"


def select_long_notes(df: pd.DataFrame) -> pd.DataFrame:
    """Pick long notes spread across specialties, in a stable order.

    Duplicate transcriptions are dropped. Notes of at least MIN_CHARS are
    preferred so each one fills more than a single fax page.
    """
    notes = df.copy()
    notes["transcription"] = notes["transcription"].fillna("").astype(str).str.strip()
    notes = notes[notes["transcription"].str.len() > 0]
    notes = notes.sort_values(
        ["transcription", "medical_specialty", "sample_name"],
        kind="mergesort",
    )
    notes = notes.drop_duplicates(subset=["transcription"], keep="first")
    notes = notes.assign(_len=notes["transcription"].str.len())

    long_notes = notes[notes["_len"] >= MIN_CHARS]
    pool = long_notes if len(long_notes) >= NOTE_COUNT else notes
    pool = pool.copy()
    pool["_rank"] = pool.groupby("medical_specialty")["_len"].rank(method="first", ascending=False)
    pool = pool.sort_values(["_rank", "medical_specialty", "sample_name"], kind="mergesort")
    return pool.head(NOTE_COUNT)


def fetch_medical_transcriptions() -> None:
    print("[*] Downloading MTSamples dataset from Hugging Face...")
    dataset = load_dataset(DATASET_ID, split="train")
    df = dataset.to_pandas()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RAW_DIR / "clinical_notes_full.csv"
    df.to_csv(csv_path, index=False)
    print(f"[*] Saved {len(df)} clinical notes to {csv_path}")

    selected = select_long_notes(df)
    txt_dir = RAW_DIR / "text_files"
    txt_dir.mkdir(parents=True, exist_ok=True)
    for old in txt_dir.glob("*.txt"):
        old.unlink()

    for i, (_, row) in enumerate(selected.iterrows()):
        subject = _safe_specialty(row.get("medical_specialty"))
        file_path = txt_dir / f"note_{i:03d}_{subject}.txt"
        file_path.write_text(
            f"Specialty: {row.get('medical_specialty')}\n"
            f"Sample Name: {row.get('sample_name')}\n\n"
            f"{row.get('transcription') or ''}",
            encoding="utf-8",
        )

    specialties = selected["medical_specialty"].nunique()
    print(f"[*] Saved {len(selected)} long notes across {specialties} specialties to {txt_dir}")


if __name__ == "__main__":
    fetch_medical_transcriptions()
