"""Bundle long MTSamples notes into multi-page skewed, noisy fax PDFs."""

from datetime import date, timedelta
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Resolve from this file so faxes land in the repo data/ tree
# even when the script is started from another directory.
ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "data" / "reference" / "synthetic" / "mtsamples" / "text_files"
OUTPUT_DIR = ROOT / "data" / "reference" / "synthetic" / "faxes"

# Page geometry (approx 150-200 DPI letter).
PAGE_WIDTH = 1700
PAGE_HEIGHT = 2200
MARGIN_LEFT = 120
MARGIN_TOP = 120
LINE_HEIGHT = 42
MAX_LINES_PER_PAGE = (PAGE_HEIGHT - (2 * MARGIN_TOP)) // LINE_HEIGHT
CHARS_PER_LINE = 78

NOTES_PER_PACKET = 3
PACKET_COUNT = 8

CLINICS = (
    "Riverside Family Practice",
    "Harbor Medical Group",
    "Northside Internal Medicine",
    "Lakeshore Specialty Clinic",
    "Cedar Valley Health",
    "West End Consultants",
    "Oak Street Physicians",
    "Summit Community Hospital",
)

# Fixed rows so each packet carries a real table, not only prose.
LAB_ROWS = (
    ("Glucose", "142", "mg/dL", "High"),
    ("Hemoglobin", "11.8", "g/dL", "Low"),
    ("WBC", "12.4", "10*3/uL", "High"),
    ("Sodium", "136", "mmol/L", ""),
    ("Potassium", "4.2", "mmol/L", ""),
    ("Creatinine", "1.4", "mg/dL", "High"),
    ("BUN", "24", "mg/dL", "High"),
    ("Platelets", "228", "10*3/uL", ""),
    ("Hemoglobin A1c", "7.6", "%", "High"),
    ("TSH", "2.1", "mIU/L", ""),
)


def get_font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("Courier", 30)
    except OSError:
        return ImageFont.load_default(size=30)


def wrap_text(text: str, max_chars_per_line: int = CHARS_PER_LINE) -> list[str]:
    """Wrap monospaced text, preserving explicit newlines."""
    wrapped_lines: list[str] = []
    for raw_line in text.split("\n"):
        if not raw_line:
            wrapped_lines.append("")
            continue
        while len(raw_line) > max_chars_per_line:
            split_idx = raw_line.rfind(" ", 0, max_chars_per_line)
            if split_idx == -1:
                split_idx = max_chars_per_line
            wrapped_lines.append(raw_line[:split_idx])
            raw_line = raw_line[split_idx:].lstrip()
        wrapped_lines.append(raw_line)
    return wrapped_lines


def render_page(lines: list[str], font: ImageFont.ImageFont | ImageFont.FreeTypeFont) -> np.ndarray:
    """Render one page of lines onto a white letter-size image."""
    img = Image.new("L", (PAGE_WIDTH, PAGE_HEIGHT), color=255)
    draw = ImageDraw.Draw(img)
    y = MARGIN_TOP
    for line in lines[:MAX_LINES_PER_PAGE]:
        draw.text((MARGIN_LEFT, y), line, font=font, fill=0)
        y += LINE_HEIGHT
    return np.array(img)


def degrade_image(img_array: np.ndarray) -> Image.Image:
    """Skew, grain, and lightly blur a page without eroding character strokes."""
    angle = np.random.uniform(-1.5, 1.5)
    height, width = img_array.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    img_skewed = cv2.warpAffine(img_array, matrix, (width, height), borderValue=255)

    noise = np.random.normal(0, 10, img_skewed.shape).astype(np.float32)
    img_noisy = np.clip(img_skewed.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    img_soft = cv2.GaussianBlur(img_noisy, (3, 3), 0)
    _, img_final = cv2.threshold(img_soft, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(img_final)


def _pages_from_lines(
    lines: list[str],
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    header: list[str] | None = None,
) -> list[Image.Image]:
    """Flow lines across pages. Repeat header at the top of every page."""
    header = header or []
    capacity = MAX_LINES_PER_PAGE - len(header)
    if capacity < 1:
        raise ValueError("page header leaves no room for body text")
    pages: list[Image.Image] = []
    for start in range(0, len(lines), capacity):
        chunk = header + lines[start : start + capacity]
        pages.append(degrade_image(render_page(chunk, font)))
    return pages


def read_note(path: Path) -> tuple[str, str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    specialty = lines[0].removeprefix("Specialty:").strip() if lines else "Unknown"
    sample_name = lines[1].removeprefix("Sample Name:").strip() if len(lines) > 1 else path.stem
    body = "\n".join(lines[3:]) if len(lines) > 3 else ""
    return specialty, sample_name, body


def cover_lines(packet_index: int, notes: list[tuple[str, str, str]]) -> list[str]:
    received = date(2026, 1, 6) + timedelta(days=packet_index - 1)
    clinic = CLINICS[(packet_index - 1) % len(CLINICS)]
    lines = [
        "FAX TRANSMITTAL",
        "",
        f"Sending clinic: {clinic}",
        f"Date received:  {received.isoformat()}",
        f"Packet:         {packet_index:03d}",
        f"Documents:      {len(notes)} clinical notes plus laboratory report",
        "",
        "Contents",
        "--------",
    ]
    for number, (specialty, sample_name, _) in enumerate(notes, start=1):
        lines.append(f"{number}. {specialty} -- {sample_name}")
    return lines


def lab_lines(packet_index: int) -> list[str]:
    lines = [
        "LABORATORY REPORT",
        "",
        f"Packet: {packet_index:03d}",
        "",
        f"{'Analyte':<22}{'Value':>8}  {'Units':<12}Flag",
        f"{'-' * 22}{'-' * 8}  {'-' * 12}----",
    ]
    for analyte, value, units, flag in LAB_ROWS:
        lines.append(f"{analyte:<22}{value:>8}  {units:<12}{flag}")
    return lines


def render_note(
    specialty: str,
    sample_name: str,
    body: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
) -> list[Image.Image]:
    header = [
        f"Specialty: {specialty}",
        f"Sample Name: {sample_name}",
        "",
    ]
    body_lines = wrap_text(body)
    if not body_lines:
        body_lines = ["(no transcription)"]
    return _pages_from_lines(body_lines, font, header=header)


def generate_faxes() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(INPUT_DIR.glob("*.txt")) if INPUT_DIR.is_dir() else []
    needed = NOTES_PER_PACKET * PACKET_COUNT
    if len(files) < needed:
        print(f"[!] Need {needed} text files in {INPUT_DIR}, found {len(files)}. Run fetch_mtsamples.py first.")
        return

    for old in OUTPUT_DIR.glob("*_scanned.pdf"):
        old.unlink()

    print(f"[*] Generating {PACKET_COUNT} multi-page fax packets into {OUTPUT_DIR}...")
    font = get_font()
    files = files[:needed]

    for packet_index in range(1, PACKET_COUNT + 1):
        start = (packet_index - 1) * NOTES_PER_PACKET
        note_paths = files[start : start + NOTES_PER_PACKET]
        notes = [read_note(path) for path in note_paths]

        note_pages: list[Image.Image] = []
        for specialty, sample_name, body in notes:
            note_pages.extend(render_note(specialty, sample_name, body, font))
        lab_page = degrade_image(render_page(lab_lines(packet_index), font))
        cover = degrade_image(render_page(wrap_text("\n".join(cover_lines(packet_index, notes))), font))
        pages = [cover, *note_pages, lab_page]

        pdf_path = OUTPUT_DIR / f"packet_{packet_index:03d}_scanned.pdf"
        pages[0].save(
            pdf_path,
            "PDF",
            resolution=150.0,
            save_all=True,
            append_images=pages[1:],
        )
        print(f"  -> Generated: {pdf_path} ({len(pages)} pages)")


if __name__ == "__main__":
    generate_faxes()
