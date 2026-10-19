"""Rasterize a source page and draw the OCR box for the selected fact."""

from io import BytesIO
from pathlib import Path

from .provenance import scale_bbox


def render_page_png(
    pdf_path: Path,
    highlight: tuple[float, float, float, float] | None = None,
    *,
    origin: tuple[float, float] = (0.0, 0.0),
    source_size: tuple[float, float] | None = None,
    dpi: int = 110,
) -> bytes:
    import fitz
    from PIL import Image, ImageDraw

    document = fitz.open(pdf_path)
    try:
        pixmap = document[0].get_pixmap(dpi=dpi, alpha=False)
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    finally:
        document.close()

    if highlight is not None and source_size is not None and source_size[0] > 0 and source_size[1] > 0:
        scaled = scale_bbox(highlight, origin, source_size, (image.width, image.height))
        draw = ImageDraw.Draw(image)
        draw.rectangle(scaled, outline=(212, 160, 74), width=3)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
