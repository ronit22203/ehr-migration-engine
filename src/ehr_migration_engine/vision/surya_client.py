"""Run Surya on atomic fax pages and write one JSON file per page."""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path

# src/ehr_migration_engine/vision/surya_client.py -> project root
ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = ROOT / "data" / "02_triage" / "atomic_pages"
OCR_DIR = ROOT / "data" / "03_ocr"
BATCH_SIZE = 4
GGUF_REPO = "datalab-to/surya-ocr-2-gguf"


def _log(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"{stamp} [*] {message}", flush=True)


class _WaitLog:
    """Print a line every few seconds while a Surya call is blocking."""

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


def _use_cached_gguf() -> None:
    """Prefer GGUF weights already on disk so a cold start does not hang on the Hub."""
    if os.environ.get("SURYA_GGUF_LOCAL_MODEL_PATH") and os.environ.get("SURYA_GGUF_LOCAL_MMPROJ_PATH"):
        _log(f"GGUF model already set: {os.environ['SURYA_GGUF_LOCAL_MODEL_PATH']}")
        return
    from huggingface_hub import try_to_load_from_cache

    model = try_to_load_from_cache(GGUF_REPO, "surya-2.gguf")
    mmproj = try_to_load_from_cache(GGUF_REPO, "surya-2-mmproj.gguf")
    if isinstance(model, str) and isinstance(mmproj, str):
        os.environ.setdefault("SURYA_GGUF_LOCAL_MODEL_PATH", model)
        os.environ.setdefault("SURYA_GGUF_LOCAL_MMPROJ_PATH", mmproj)
        _log(f"Using cached GGUF model: {model}")
        _log(f"Using cached GGUF mmproj: {mmproj}")


def run_ocr(pages_dir: Path | None = None, ocr_dir: Path | None = None) -> None:
    """OCR each single-page PDF and store Surya's layout blocks as JSON."""
    pages_dir = pages_dir or PAGES_DIR
    ocr_dir = ocr_dir or OCR_DIR
    ocr_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pages_dir.glob("*.pdf")) if pages_dir.is_dir() else []
    if not pdfs:
        print(f"[!] No PDFs found in {pages_dir}")
        return

    pending = [path for path in pdfs if not (ocr_dir / f"{path.stem}.json").exists()]
    _log(f"{len(pdfs)} atomic pages in {pages_dir}")
    _log(f"{len(pdfs) - len(pending)} already have JSON in {ocr_dir}")
    _log(f"{len(pending)} still need OCR")
    if not pending:
        _log("OCR already complete")
        return

    _use_cached_gguf()
    os.environ.setdefault("LOGLEVEL", "DEBUG")

    # Import Surya before torch so the MPS fallback in surya/__init__.py applies.
    from surya.inference import SuryaInferenceManager
    from surya.input.load import load_pdf
    from surya.logging import configure_logging
    from surya.recognition import RecognitionPredictor
    from surya.settings import settings

    configure_logging()
    _log(
        f"Loading Surya at {settings.IMAGE_DPI_HIGHRES} DPI, "
        f"batch size {BATCH_SIZE}, log level {settings.LOGLEVEL}"
    )
    _log("Creating the inference client. This attaches to llama-server or starts one.")
    started = time.perf_counter()
    predictor = RecognitionPredictor(SuryaInferenceManager())
    _log(f"Inference client ready in {time.perf_counter() - started:.1f}s")

    batches = range(0, len(pending), BATCH_SIZE)
    batch_total = (len(pending) + BATCH_SIZE - 1) // BATCH_SIZE
    done = 0
    for batch_index, start in enumerate(batches, start=1):
        batch = pending[start : start + BATCH_SIZE]
        names = ", ".join(path.name for path in batch)
        _log(f"Batch {batch_index}/{batch_total}: rasterizing {len(batch)} pages ({names})")
        images = []
        for pdf_path in batch:
            raster_started = time.perf_counter()
            page_images, _names = load_pdf(str(pdf_path), dpi=settings.IMAGE_DPI_HIGHRES)
            image = page_images[0]
            images.append(image)
            _log(
                f"  raster {pdf_path.name}: {image.size[0]}x{image.size[1]} "
                f"in {time.perf_counter() - raster_started:.2f}s"
            )

        _log(f"Batch {batch_index}/{batch_total}: Surya full-page OCR started")
        _log("No page is written until this batch returns. A quiet stretch here is the model generating.")
        infer_started = time.perf_counter()
        with _WaitLog(f"Batch {batch_index}/{batch_total}: llama-server is generating"):
            results = predictor(images, full_page=True)
        _log(
            f"Batch {batch_index}/{batch_total}: Surya returned in "
            f"{time.perf_counter() - infer_started:.1f}s"
        )
        for pdf_path, page in zip(batch, results, strict=True):
            payload = {"source": pdf_path.name, **page.model_dump(mode="json")}
            out_path = ocr_dir / f"{pdf_path.stem}.json"
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            labels = ", ".join(block.label for block in page.blocks) or "none"
            done += 1
            _log(
                f"  wrote {out_path.name} ({len(page.blocks)} blocks: {labels}) "
                f"[{done}/{len(pending)}]"
            )


if __name__ == "__main__":
    run_ocr()
