"""Turn clean MTSamples notes into skewed, noisy, 1-bit fax PDFs."""

import textwrap
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Resolve from this file so faxes land in the repo data/ tree
# even when the script is started from another directory.
ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "data" / "01_raw" / "mtsamples" / "text_files"
OUTPUT_DIR = ROOT / "data" / "01_raw" / "faxes"

PAGE_WIDTH = 1700
PAGE_HEIGHT = 2200
MARGIN_X = 100
MARGIN_Y = 100
LINE_HEIGHT = 40
CHARS_PER_LINE = 70


def _font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("Courier", 30)
    except OSError:
        return ImageFont.load_default(size=30)


def text_to_image(text: str) -> np.ndarray:
    """Render text onto a clean white letter-size image."""
    img = Image.new("L", (PAGE_WIDTH, PAGE_HEIGHT), color=255)
    draw = ImageDraw.Draw(img)
    font = _font()

    y_text = MARGIN_Y
    for raw_line in text.split("\n"):
        wrapped = textwrap.wrap(raw_line, width=CHARS_PER_LINE) or [""]
        for line in wrapped:
            if y_text > PAGE_HEIGHT - MARGIN_Y:
                return np.array(img)
            draw.text((MARGIN_X, y_text), line, font=font, fill=0)
            y_text += LINE_HEIGHT
    return np.array(img)


def degrade_image(img_array: np.ndarray) -> np.ndarray:
    """Apply severe physical degradation to simulate a bad fax or scan."""
    angle = np.random.uniform(-2.5, 2.5)
    height, width = img_array.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    img_rotated = cv2.warpAffine(img_array, matrix, (width, height), borderValue=255)

    noise = np.random.normal(0, 25, img_rotated.shape).astype(np.uint8)
    img_noisy = cv2.add(img_rotated, noise)
    img_blurred = cv2.GaussianBlur(img_noisy, (5, 5), 0)

    _, img_thresh = cv2.threshold(img_blurred, 150, 255, cv2.THRESH_BINARY)
    return img_thresh


def generate_faxes() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(INPUT_DIR.glob("*.txt")) if INPUT_DIR.is_dir() else []
    if not files:
        print(f"[!] No text files found in {INPUT_DIR}. Run fetch_mtsamples.py first.")
        return

    print(f"[*] Generating degraded fax PDFs into {OUTPUT_DIR}...")
    for path in files[:5]:
        text = path.read_text(encoding="utf-8")[:2000]
        dirty_img = degrade_image(text_to_image(text))
        pdf_path = OUTPUT_DIR / f"{path.stem}_scanned.pdf"
        Image.fromarray(dirty_img).save(pdf_path, "PDF", resolution=150.0)
        print(f"  -> Generated: {pdf_path}")


if __name__ == "__main__":
    generate_faxes()
