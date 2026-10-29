"""Fetch degraded medical scans from the UCSF Truth Tobacco Industry Documents.

Uses the public IDL Solr metadata API to find chart / discharge / lab layouts,
then pulls PDFs from the public `ucsf-idl-dataset` S3 bucket (no login required).

These are born-analog litigation scans: faxed, Bates-stamped, hole-punched, and
re-scanned — ideal adversarial OCR input for Surya + the spatial parser.
"""

from __future__ import annotations

import argparse
from typing import Any

from common import (
    ROOT,
    download_file,
    encode_query,
    get_json,
    group_dir,
    safe_stem,
    stage_into_faxes,
    write_manifest,
)

GROUP = "01_ucsf_tobacco"
SOLR = "https://metadata.idl.ucsf.edu/solr/ltdl3/query"
DATASET = "https://ucsf-idl-dataset.s3.us-east-1.amazonaws.com"

# Prefer authentic medical layouts over tobacco-marketing ephemera.
DEFAULT_QUERIES = (
    'title:("discharge summary")',
    'title:("patient chart" OR "hospital chart" OR "medical chart")',
    'title:("lab report" OR "laboratory report" OR "lab results")',
    'title:("progress note" OR "consult" OR "consultation") AND type:(medical OR "medical record" OR note OR chart)',
    '"discharge summary" AND type:(medical OR "medical record" OR report OR chart)',
)

# Soft preference for document types that look like clinical packets.
TYPE_BOOST = (
    "chart",
    "medical",
    "medical record",
    "report",
    "note",
    "form",
)

TITLE_HIT = (
    "discharge summary",
    "patient chart",
    "hospital chart",
    "medical chart",
    "lab report",
    "laboratory report",
    "lab results",
    "progress note",
    "consult",
    "medical record",
    "history and physical",
    "operative report",
)

TITLE_REJECT = (
    "inventory",
    "storage",
    "retake log",
    "shipping",
    "index",
    "privilege log",
    "bates",
    "production log",
    "transmittal",
    "metallurgical",
    "engineering",
    "chemical laboratory",
    "research committee grant",
)


def dataset_pdf_url(doc_id: str) -> str:
    """Map an 8-char IDL id to its public dataset PDF key."""
    doc_id = doc_id.lower()
    a, b, c, d = doc_id[0], doc_id[1], doc_id[2], doc_id[3]
    return f"{DATASET}/{a}/{b}/{c}/{d}/{doc_id}/{doc_id}.pdf"


def is_public(doc: dict[str, Any]) -> bool:
    availability = [str(x).lower() for x in (doc.get("availability") or [])]
    if "restricted" in availability or "confidential" in availability:
        return False
    return "public" in availability or "no restrictions" in availability


def type_score(doc: dict[str, Any]) -> int:
    types = {str(x).lower() for x in (doc.get("type") or [])}
    return sum(1 for t in TYPE_BOOST if t in types)


def title_score(doc: dict[str, Any]) -> int | None:
    title = str(doc.get("title") or "").lower()
    if any(bad in title for bad in TITLE_REJECT):
        return None
    hits = sum(1 for needle in TITLE_HIT if needle in title)
    return hits if hits > 0 else None


def search_docs(query: str, *, rows: int) -> list[dict[str, Any]]:
    url = encode_query(
        SOLR,
        {
            "q": query,
            "wt": "json",
            "rows": rows,
            "fl": "id,title,pages,type,format,availability,collection,documentdate",
        },
    )
    payload = get_json(url, timeout=90.0)
    return list(payload.get("response", {}).get("docs") or [])


def select_candidates(limit: int, *, per_query: int, max_pages: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    ranked: list[tuple[int, dict[str, Any]]] = []

    for query in DEFAULT_QUERIES:
        print(f"[*] Searching IDL for: {query}")
        try:
            docs = search_docs(query, rows=per_query)
        except Exception as exc:  # noqa: BLE001 - keep other queries running
            print(f"[warn] Solr query failed ({query}): {exc}")
            continue
        for doc in docs:
            doc_id = str(doc.get("id") or "").lower()
            if not doc_id or doc_id in seen or not is_public(doc):
                continue
            pages = int(doc.get("pages") or 0)
            if pages <= 0 or pages > max_pages:
                continue
            title_hits = title_score(doc)
            if title_hits is None:
                continue
            # Prefer scanned hardcopy when the field is present.
            fmt = str(doc.get("format") or "").lower()
            score = type_score(doc) + (3 * title_hits)
            if "scan" in fmt:
                score += 2
            seen.add(doc_id)
            ranked.append((score, doc))

    ranked.sort(key=lambda item: (-item[0], str(item[1].get("id"))))
    return [doc for _, doc in ranked[:limit]]


def fetch(limit: int, *, stage: int, max_pages: int, per_query: int) -> None:
    out = group_dir(GROUP)
    candidates = select_candidates(limit, per_query=per_query, max_pages=max_pages)
    if not candidates:
        raise SystemExit("No public medical-layout candidates found in IDL.")

    saved: list[dict[str, Any]] = []
    paths = []
    for doc in candidates:
        doc_id = str(doc["id"]).lower()
        title = str(doc.get("title") or doc_id)
        stem = safe_stem(f"{doc_id}_{title}")
        dest = out / f"{stem}.pdf"
        url = dataset_pdf_url(doc_id)
        ok = download_file(url, dest)
        if not ok:
            continue
        paths.append(dest)
        saved.append(
            {
                "id": doc_id,
                "title": title,
                "pages": doc.get("pages"),
                "type": doc.get("type"),
                "format": doc.get("format"),
                "collection": doc.get("collection"),
                "documentdate": doc.get("documentdate"),
                "source_url": url,
                "viewer_url": f"https://www.industrydocuments.ucsf.edu/docs/{doc_id}",
                "path": str(dest.relative_to(ROOT)),
            }
        )

    write_manifest(
        out / "manifest.json",
        {
            "group": GROUP,
            "source": "UCSF Truth Tobacco Industry Documents / IDL public dataset",
            "solr": SOLR,
            "queries": list(DEFAULT_QUERIES),
            "count": len(saved),
            "documents": saved,
        },
    )

    if stage > 0 and paths:
        stage_into_faxes(paths[:stage], prefix="ucsf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=8, help="Max PDFs to download")
    parser.add_argument(
        "--stage",
        type=int,
        default=3,
        help="Copy this many into data/01_raw/faxes (0 to skip)",
    )
    parser.add_argument("--max-pages", type=int, default=25, help="Skip longer packets")
    parser.add_argument(
        "--per-query",
        type=int,
        default=40,
        help="Solr rows fetched per search string",
    )
    args = parser.parse_args()
    fetch(args.limit, stage=args.stage, max_pages=args.max_pages, per_query=args.per_query)


if __name__ == "__main__":
    main()
