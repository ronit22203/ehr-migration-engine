"""Shared helpers for real-world OCR stress-test downloads."""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = ROOT / "data" / "reference" / "real_world"
FAXES_DIR = ROOT / "data" / "01_raw" / "faxes"

USER_AGENT = (
    "ehr-migration-engine/0.1 "
    "(+https://github.com/local/ehr-migration-engine; OCR stress-test corpus)"
)


def group_dir(name: str) -> Path:
    path = REFERENCE_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_faxes_dir() -> Path:
    FAXES_DIR.mkdir(parents=True, exist_ok=True)
    return FAXES_DIR


def safe_stem(value: str, *, max_len: int = 80) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned or "document")[:max_len]


def download_file(
    url: str,
    dest: Path,
    *,
    timeout: float = 60.0,
    retries: int = 3,
    sleep_s: float = 1.0,
) -> bool:
    """Download url into dest. Returns True on success, False on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] already have {dest.name}")
        return True

    tmp = dest.with_suffix(dest.suffix + ".partial")
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = (resp.headers.get_content_type() or "").lower()
                data = resp.read()
            if not data:
                raise RuntimeError("empty response body")
            # Reject HTML error pages that still return HTTP 200.
            if "html" in content_type and not data.startswith(b"%PDF"):
                raise RuntimeError(f"non-PDF content-type: {content_type}")
            if dest.suffix.lower() == ".pdf" and not data.startswith(b"%PDF"):
                raise RuntimeError("response is not a PDF")
            tmp.write_bytes(data)
            tmp.replace(dest)
            print(f"[ok]   {dest.name} ({len(data):,} bytes)")
            return True
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
            last_error = exc
            print(f"[warn] attempt {attempt}/{retries} failed for {url}: {exc}")
            if attempt < retries:
                time.sleep(sleep_s * attempt)

    print(f"[fail] {url}" + (f" ({last_error})" if last_error else ""))
    if tmp.exists():
        tmp.unlink(missing_ok=True)
    return False


def stage_into_faxes(paths: list[Path], *, prefix: str) -> list[Path]:
    """Copy selected PDFs into the live OCR drop with a stable prefix."""
    ensure_faxes_dir()
    staged: list[Path] = []
    for src in paths:
        if not src.exists() or src.suffix.lower() != ".pdf":
            continue
        dest = FAXES_DIR / f"{prefix}_{src.name}"
        shutil.copy2(src, dest)
        staged.append(dest)
        print(f"[stage] {dest.relative_to(ROOT)}")
    return staged


def write_manifest(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[*] Wrote manifest {path.relative_to(ROOT)}")


def get_json(url: str, *, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def encode_query(base: str, params: dict[str, str | int]) -> str:
    query = urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    return f"{base}?{query}"
