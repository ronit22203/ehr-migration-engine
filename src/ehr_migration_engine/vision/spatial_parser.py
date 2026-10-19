import json
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[3]
OCR_DIR = ROOT / "data" / "03_ocr"
TEXT_DIR = OCR_DIR / "parsed_text"


def clean_html_to_text(html_content: str) -> str:
    """Strip HTML tags and return clean text."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n").strip()


def reconstruct_documents() -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    json_files = sorted(OCR_DIR.glob("*.json"))
    if not json_files:
        print(f"[!] No OCR JSON files found in {OCR_DIR}")
        return

    print(f"[*] Reconstructing {len(json_files)} pages into plain text...")

    for json_path in json_files:
        output_txt_path = TEXT_DIR / f"{json_path.stem}.txt"

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        blocks = data.get("blocks", [])
        blocks.sort(key=lambda x: x.get("reading_order", 9999))

        page_text_blocks = []
        for block in blocks:
            clean_text = clean_html_to_text(block.get("html", ""))
            if clean_text:
                page_text_blocks.append(clean_text)

        full_page_text = "\n\n".join(page_text_blocks)

        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(full_page_text)

    print(f"[*] Parsing complete. Clean text saved to {TEXT_DIR}")


if __name__ == "__main__":
    reconstruct_documents()
