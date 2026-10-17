"""Split multi-page unstructured PDFs into single-page files for OCR."""

from pathlib import Path

from pypdf import PdfReader, PdfWriter

# src/ehr_migration_engine/ingestion/pdf_handler.py -> project root
ROOT = Path(__file__).resolve().parents[3]
TRIAGE_DIR = ROOT / "data" / "02_triage"


def decouple_pdfs(triage_dir: Path | None = None) -> None:
    """Split each unstructured PDF into one file per page.

    Pages are written as ``<stem>_page_001.pdf`` under ``atomic_pages``.
    """
    triage_dir = triage_dir or TRIAGE_DIR
    unstructured_dir = triage_dir / "unstructured"
    atomic_dir = triage_dir / "atomic_pages"
    atomic_dir.mkdir(parents=True, exist_ok=True)

    print("[*] Starting Phase 1: PDF Decoupling...")

    pdf_files = sorted(unstructured_dir.glob("*.pdf")) if unstructured_dir.is_dir() else []
    if not pdf_files:
        print(f"[!] No PDFs found in {unstructured_dir}")
        return

    for pdf_path in pdf_files:
        try:
            reader = PdfReader(pdf_path)
            for i, page in enumerate(reader.pages):
                writer = PdfWriter()
                writer.add_page(page)
                output_path = atomic_dir / f"{pdf_path.stem}_page_{i + 1:03d}.pdf"
                with output_path.open("wb") as out_file:
                    writer.write(out_file)
            print(f"  -> Split: {pdf_path.name} ({len(reader.pages)} pages)")
        except Exception as exc:
            print(f"  [X] Error processing {pdf_path.name}: {exc}")


if __name__ == "__main__":
    decouple_pdfs()
