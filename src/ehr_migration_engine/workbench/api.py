"""FastAPI shell for the clinical migration workbench."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ehr_migration_engine.graph.timeline import ClinicalGraph
from ehr_migration_engine.workbench.catalog import BatchCatalog, PageArtifacts, load_catalog
from ehr_migration_engine.workbench.facts import Fact, facts_from_extraction
from ehr_migration_engine.workbench.paths import PROJECT_ROOT, layout_for, read_json
from ehr_migration_engine.workbench.provenance import ProvenanceLink, link_facts, source_frame
from ehr_migration_engine.workbench.render import render_page_png
from ehr_migration_engine.workbench.review import ReviewEntry, ReviewLedger, effective_value
from ehr_migration_engine.workbench.status import page_flags, summarize

UI_DIST = PROJECT_ROOT / "workbench-ui" / "dist"

app = FastAPI(title="EHR migration workbench", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReviewBody(BaseModel):
    field_path: str
    status: Literal["accepted", "rejected", "corrected"]
    revised_value: str | None = None
    reason: str | None = None
    code_system: str | None = None
    code: str | None = None
    display: str | None = None


def _root() -> Path:
    override = os.environ.get("EHR_MIGRATION_ROOT")
    return Path(override).resolve() if override else PROJECT_ROOT


def _catalog() -> BatchCatalog:
    return load_catalog(_root())


def _ledger() -> ReviewLedger:
    return ReviewLedger(layout_for(_root()).ledger)


def _find_page(stem: str) -> PageArtifacts:
    page = next((item for item in _catalog().pages() if item.stem == stem), None)
    if page is None:
        raise HTTPException(status_code=404, detail=f"Unknown page: {stem}")
    return page


def _extraction(page: PageArtifacts) -> dict | None:
    data = read_json(page.structured_json)
    return data if isinstance(data, dict) else None


def _error(page: PageArtifacts) -> dict | None:
    if page.structured_json is not None:
        return None
    data = read_json(page.error_json)
    return data if isinstance(data, dict) else None


def _ocr(page: PageArtifacts) -> dict | None:
    data = read_json(page.ocr_json)
    return data if isinstance(data, dict) else None


def _fact_dict(fact: Fact) -> dict[str, Any]:
    return asdict(fact)


def _entry_dict(entry: ReviewEntry) -> dict[str, Any]:
    return asdict(entry)


def _link_dict(link: ProvenanceLink) -> dict[str, Any]:
    payload = asdict(link)
    if link.bbox is not None:
        payload["bbox"] = list(link.bbox)
    return payload


def _source_name(page: PageArtifacts, ocr: dict | None) -> str | None:
    if isinstance(ocr, dict) and isinstance(ocr.get("source"), str) and ocr["source"].strip():
        return ocr["source"].strip()
    if page.atomic_pdf is not None:
        return page.atomic_pdf.name
    return None


def _parsed_text(page: PageArtifacts) -> str:
    if page.parsed_text is None or not page.parsed_text.is_file():
        return ""
    return page.parsed_text.read_text(encoding="utf-8")


def _plain_block(block: dict) -> str:
    from ehr_migration_engine.vision.spatial_parser import clean_html_to_text

    html_text = block.get("html")
    if isinstance(html_text, str) and html_text.strip():
        return clean_html_to_text(html_text)
    return ""


def _code_system_placeholder(kind: str) -> str:
    if kind == "Medication":
        return "http://www.nlm.nih.gov/research/umls/rxnorm"
    if kind == "Observation":
        return "http://loinc.org"
    return "http://snomed.info/sct"


def _fact_label(fact: Fact) -> str:
    shown = fact.value
    if fact.kind == "Observation" and fact.result:
        shown = " ".join(part for part in (fact.value, fact.result, fact.units, fact.flag) if part)
    if len(shown) > 72:
        shown = shown[:69] + "..."
    return f"{fact.kind}  {shown}"


def _fact_needs_code(entry: ReviewEntry | None) -> bool:
    if entry is not None and entry.status == "rejected":
        return False
    return entry is None or not (entry.code and entry.code_system and entry.status in {"accepted", "corrected"})


def _check_rows(
    page: PageArtifacts,
    fact: Fact | None,
    link: ProvenanceLink | None,
    entry: ReviewEntry | None,
) -> list[dict[str, str]]:
    if page.structured_json is not None:
        schema = "Passed"
    elif page.error_json is not None:
        schema = "Failed"
    else:
        schema = "Pending"
    if fact is None:
        rows = [("Schema", schema), ("Terminology", "Pending"), ("Provenance", "Pending")]
    else:
        if not fact.requires_code:
            terminology = "Not required"
        elif entry and entry.status == "rejected":
            terminology = "Rejected"
        elif entry and entry.status in {"accepted", "corrected"} and entry.code and entry.code_system:
            terminology = "Passed"
        else:
            terminology = "Review"
        provenance = "Linked" if link and link.resolved else "Unresolved"
        rows = [("Schema", schema), ("Terminology", terminology), ("Provenance", provenance)]
    return [{"label": label, "state": state} for label, state in rows]


def _validate_review(fact: Fact, body: ReviewBody) -> str | None:
    reason = (body.reason or "").strip()
    revised = (body.revised_value or "").strip()
    system = (body.code_system or "").strip()
    code = (body.code or "").strip()
    display = (body.display or "").strip()
    if body.status == "rejected" and not reason:
        return "A rejection needs a reason."
    if body.status == "corrected" and (not revised or not reason):
        return "A correction needs a revised value and a reason."
    coded = bool(system or code or display)
    if fact.requires_code and body.status == "accepted" and not (system and code and display):
        return "This record needs a code system, code, and display before it can be accepted."
    if body.status == "corrected" and coded and not (system and code and display):
        return "A code needs a system, code, and display."
    return None


@app.get("/api/batch")
def get_batch() -> dict[str, Any]:
    catalog = _catalog()
    ledger = _ledger()
    reviews_by_stem = ledger.by_stem()
    facts_by_stem = {
        page.stem: facts_from_extraction(_extraction(page)) for page in catalog.pages()
    }
    flags = {
        page.stem: page_flags(page, facts_by_stem.get(page.stem, []), reviews_by_stem.get(page.stem, {}))
        for page in catalog.pages()
    }
    counts = summarize(catalog, facts_by_stem, reviews_by_stem)
    packets = []
    for packet in catalog.packets:
        pages = []
        for page in packet.pages:
            page_flags_obj = flags[page.stem]
            pages.append(
                {
                    "stem": page.stem,
                    "page_number": page.page_number,
                    "marker": page_flags_obj.marker,
                    "missing": page_flags_obj.missing,
                    "pending": page_flags_obj.pending,
                    "reviewed": page_flags_obj.reviewed,
                    "failed": page_flags_obj.failed,
                    "has_ocr": page.ocr_json is not None,
                    "has_structured": page.structured_json is not None,
                    "has_error": page.error_json is not None and page.structured_json is None,
                    "has_atomic": page.atomic_pdf is not None,
                }
            )
        packets.append(
            {
                "stem": packet.stem,
                "filename": packet.filename,
                "pages": pages,
            }
        )
    coverage = []
    failures = []
    for page in catalog.pages():
        error = _error(page)
        coverage.append(
            {
                "page": page.stem,
                "ocr": "yes" if page.ocr_json else "no",
                "structured": "yes" if page.structured_json else "no",
                "failure": error.get("error_type", "") if error else "",
                "reviews": len(reviews_by_stem.get(page.stem, {})),
            }
        )
        if error:
            failures.append(
                {
                    "page": page.stem,
                    "type": error.get("error_type", ""),
                    "attempts": error.get("attempts", ""),
                    "message": error.get("message", ""),
                }
            )
    events = [
        {
            "time": entry.timestamp,
            "page": entry.stem,
            "field": entry.field_path,
            "status": entry.status,
        }
        for entry in ledger.entries()[-30:]
    ]
    return {
        "batch_id": catalog.batch_id,
        "counts": asdict(counts),
        "packets": packets,
        "coverage": coverage,
        "failures": failures,
        "review_events": events,
    }


@app.get("/api/pages/{stem}")
def get_page(stem: str, field_path: str | None = None) -> dict[str, Any]:
    page = _find_page(stem)
    extraction = _extraction(page)
    error = _error(page)
    ocr = _ocr(page)
    facts = facts_from_extraction(extraction)
    reviews = _ledger().latest_for(stem)
    source_file = _source_name(page, ocr)
    links = link_facts(ocr, facts, source_file=source_file, page_number=page.page_number or None)
    link_by_field = {link.field_path: link for link in links}
    selected = next((fact for fact in facts if fact.field_path == field_path), None) if field_path else None
    selected_link = link_by_field.get(selected.field_path) if selected else None
    selected_entry = reviews.get(selected.field_path) if selected else None
    fhir_path = layout_for(_root()).fhir / f"{page.stem}.json"
    return {
        "stem": page.stem,
        "page_number": page.page_number,
        "packet_stem": page.packet_stem,
        "extraction": extraction,
        "error": error,
        "facts": [
            {
                **_fact_dict(fact),
                "label": _fact_label(fact),
                "effective_value": effective_value(fact.value, reviews.get(fact.field_path)),
                "code_system_placeholder": _code_system_placeholder(fact.kind),
                "needs_code": fact.requires_code and _fact_needs_code(reviews.get(fact.field_path)),
                "review": _entry_dict(reviews[fact.field_path]) if fact.field_path in reviews else None,
                "provenance": _link_dict(link_by_field[fact.field_path])
                if fact.field_path in link_by_field
                else None,
            }
            for fact in facts
        ],
        "selected_field": selected.field_path if selected else None,
        "checks": _check_rows(page, selected, selected_link, selected_entry),
        "has_atomic": page.atomic_pdf is not None,
        "has_ocr": page.ocr_json is not None,
        "has_fhir": fhir_path.is_file(),
        "patient_name": extraction.get("patient_name") if isinstance(extraction, dict) else None,
    }


@app.get("/api/pages/{stem}/source.png")
def get_source_png(
    stem: str,
    field_path: str | None = None,
) -> Response:
    page = _find_page(stem)
    if page.atomic_pdf is None:
        raise HTTPException(status_code=404, detail="This page has not been split.")
    ocr = _ocr(page)
    highlight = None
    origin = (0.0, 0.0)
    source_size = None
    if field_path:
        extraction = _extraction(page)
        facts = facts_from_extraction(extraction)
        fact = next((item for item in facts if item.field_path == field_path), None)
        if fact is not None:
            links = link_facts(
                ocr,
                [fact],
                source_file=_source_name(page, ocr),
                page_number=page.page_number or None,
            )
            link = links[0] if links else None
            if link and link.resolved and link.bbox is not None:
                highlight = link.bbox
            frame = source_frame(ocr)
            if frame:
                origin, source_size = frame
    try:
        png = render_page_png(page.atomic_pdf, highlight, origin=origin, source_size=source_size)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not render this page ({type(exc).__name__}).") from exc
    return Response(content=png, media_type="image/png")


@app.get("/api/pages/{stem}/ocr")
def get_ocr(stem: str, field_path: str | None = None) -> dict[str, Any]:
    page = _find_page(stem)
    ocr = _ocr(page)
    if ocr is None:
        return {"available": False, "parsed_text": _parsed_text(page), "blocks": []}
    blocks = ocr.get("blocks")
    matched = None
    if field_path and isinstance(blocks, list):
        extraction = _extraction(page)
        facts = facts_from_extraction(extraction)
        fact = next((item for item in facts if item.field_path == field_path), None)
        if fact is not None:
            links = link_facts(
                ocr,
                [fact],
                source_file=_source_name(page, ocr),
                page_number=page.page_number or None,
            )
            if links and links[0].resolved:
                matched = links[0].block_index
    parts: list[dict[str, Any]] = []
    if isinstance(blocks, list):
        indexed = [(index, block) for index, block in enumerate(blocks) if isinstance(block, dict)]
        indexed.sort(key=lambda item: item[1].get("reading_order", 9999))
        for index, block in indexed:
            text = _plain_block(block)
            if not text:
                continue
            parts.append(
                {
                    "index": index,
                    "matched": index == matched,
                    "text": text,
                    "label": block.get("label"),
                    "reading_order": block.get("reading_order"),
                }
            )
    return {
        "available": True,
        "matched_block": matched,
        "blocks": parts,
        "parsed_text": _parsed_text(page),
    }


@app.get("/api/pages/{stem}/clinical")
def get_clinical(stem: str) -> dict[str, Any]:
    page = _find_page(stem)
    extraction = _extraction(page)
    if extraction is not None:
        path = page.structured_json
        rel = str(path.relative_to(_root())) if path else None
        return {"available": True, "path": rel, "data": extraction, "error": None}
    error = _error(page)
    if error is not None:
        return {"available": False, "path": None, "data": None, "error": error}
    return {"available": False, "path": None, "data": None, "error": None}


@app.get("/api/pages/{stem}/fhir")
def get_fhir(stem: str) -> dict[str, Any]:
    page = _find_page(stem)
    path = layout_for(_root()).fhir / f"{page.stem}.json"
    bundle = read_json(path)
    if not isinstance(bundle, dict):
        return {"available": False, "path": None, "bundle": None, "summary": None}
    entries = bundle.get("entry")
    kinds: list[str] = []
    if isinstance(entries, list):
        for item in entries:
            resource = item.get("resource") if isinstance(item, dict) else None
            if isinstance(resource, dict) and isinstance(resource.get("resourceType"), str):
                kinds.append(resource["resourceType"])
    summary = ", ".join(f"{kinds.count(kind)} {kind}" for kind in dict.fromkeys(kinds))
    try:
        rel = str(path.relative_to(_root()))
    except ValueError:
        rel = path.name
    return {
        "available": True,
        "path": rel,
        "bundle": bundle,
        "summary": summary or None,
        "count": len(entries) if isinstance(entries, list) else 0,
        "type": bundle.get("type"),
    }


@app.get("/api/patients/{name}/timeline")
def get_timeline(name: str) -> dict[str, Any]:
    patient = unquote(name).strip()
    if not patient:
        raise HTTPException(status_code=400, detail="Patient name is required.")
    graph = None
    try:
        graph = ClinicalGraph()
        graph.driver.verify_connectivity()
        pages = graph.patient_timeline(patient)
    except Exception as exc:
        return {
            "available": False,
            "patient_name": patient,
            "pages": [],
            "error": str(exc),
            "hint": "docker compose up -d && make graph",
        }
    finally:
        if graph is not None:
            graph.close()
    return {"available": True, "patient_name": patient, "pages": pages, "error": None, "hint": None}


@app.post("/api/pages/{stem}/review")
def post_review(stem: str, body: ReviewBody) -> dict[str, Any]:
    page = _find_page(stem)
    extraction = _extraction(page)
    facts = facts_from_extraction(extraction)
    fact = next((item for item in facts if item.field_path == body.field_path), None)
    if fact is None:
        raise HTTPException(status_code=404, detail=f"Unknown field: {body.field_path}")
    error = _validate_review(fact, body)
    if error:
        raise HTTPException(status_code=400, detail=error)
    try:
        entry = _ledger().record(
            stem=page.stem,
            field_path=fact.field_path,
            status=body.status,
            original_value=fact.value,
            revised_value=body.revised_value if body.status == "corrected" else None,
            code_system=body.code_system if fact.requires_code and body.status in {"accepted", "corrected"} else None,
            code=body.code if fact.requires_code and body.status in {"accepted", "corrected"} else None,
            display=body.display if fact.requires_code and body.status in {"accepted", "corrected"} else None,
            reason=body.reason or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "entry": _entry_dict(entry)}


if UI_DIST.is_dir():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
