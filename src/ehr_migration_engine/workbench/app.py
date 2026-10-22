"""Clinical migration workbench. Reads pipeline artifacts; does not rerun the pipeline."""

import html
import importlib
import json
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from ehr_migration_engine.graph.timeline import ClinicalGraph
from ehr_migration_engine.workbench.catalog import BatchCatalog, PageArtifacts, load_catalog
from ehr_migration_engine.workbench.facts import Fact, facts_from_extraction
from ehr_migration_engine.workbench.paths import layout_for, read_json
from ehr_migration_engine.workbench.provenance import ProvenanceLink, link_facts, source_frame
from ehr_migration_engine.workbench.render import render_page_png
from ehr_migration_engine.workbench.review import ReviewEntry, ReviewLedger, effective_value
from ehr_migration_engine.workbench.status import PageFlags, matches_filter, page_flags, summarize
from ehr_migration_engine.workbench import theme as workbench_theme

STAGES = (
    "Overview",
    "Ingestion",
    "OCR",
    "Extraction",
    "Normalization",
    "Patient Timeline",
    "FHIR",
)
VIEWS = ("Source", "OCR", "Clinical JSON", "FHIR")
STAGE_VIEW = {
    "Overview": "Source",
    "Ingestion": "Source",
    "OCR": "OCR",
    "Extraction": "Clinical JSON",
    "Normalization": "Clinical JSON",
    "Patient Timeline": "Source",
    "FHIR": "FHIR",
}
FILTERS = ("All", "Missing", "Pending", "Reviewed")
_VIEWER_STAGES = {"Ingestion", "OCR", "Extraction", "Normalization", "FHIR"}
_STATE_CLASS = {
    "Passed": "wb-ok",
    "Linked": "wb-ok",
    "Not required": "wb-muted",
    "Review": "wb-review",
    "Pending": "wb-review",
    "Unresolved": "wb-review",
    "Failed": "wb-bad",
    "Rejected": "wb-bad",
}
_OPEN = {"Pending", "Review", "Unresolved"}


@dataclass
class Selection:
    page: PageArtifacts | None
    extraction: dict | None
    ocr: dict | None
    error: dict | None
    facts: list[Fact]
    links: list[ProvenanceLink]
    reviews: dict[str, ReviewEntry]
    fact: Fact | None
    link: ProvenanceLink | None
    entry: ReviewEntry | None


def main() -> None:
    st.set_page_config(page_title="Migration workbench", layout="wide", initial_sidebar_state="collapsed")
    importlib.reload(workbench_theme)
    st.markdown(workbench_theme.CSS, unsafe_allow_html=True)
    _init_state()

    layout = layout_for()
    catalog = load_catalog(layout.root)
    ledger = ReviewLedger(layout.ledger)
    reviews_by_stem = ledger.by_stem()
    facts_by_stem = {
        page.stem: facts_from_extraction(_json_for(page.structured_json)) for page in catalog.pages()
    }
    flags = {
        page.stem: page_flags(page, facts_by_stem.get(page.stem, []), reviews_by_stem.get(page.stem, {}))
        for page in catalog.pages()
    }
    _ensure_selection(catalog)
    selection = _selection(catalog, facts_by_stem, reviews_by_stem)

    _header(catalog.batch_id)
    left, center, right = st.columns([1.15, 3.35, 1.7], gap="small")
    with left:
        _explorer(catalog, flags)
    with center:
        _center(selection, layout.root)
    with right:
        if _inspector(selection, ledger):
            st.rerun()
    _console(catalog, ledger, reviews_by_stem)


def _init_state() -> None:
    st.session_state.setdefault("stage", "Overview")
    st.session_state.setdefault("center_view", "Source")
    st.session_state.setdefault("selected_stem", None)
    st.session_state.setdefault("selected_field", None)
    st.session_state.setdefault("explorer_filter", "All")
    st.session_state.setdefault("action_error", None)


def _ensure_selection(catalog: BatchCatalog) -> None:
    stems = {page.stem for page in catalog.pages()}
    if st.session_state.selected_stem not in stems:
        pages = catalog.pages()
        st.session_state.selected_stem = pages[0].stem if pages else None
        st.session_state.selected_field = None


def _selection(
    catalog: BatchCatalog,
    facts_by_stem: dict[str, list[Fact]],
    reviews_by_stem: dict[str, dict[str, ReviewEntry]],
) -> Selection:
    page = _find_page(catalog, st.session_state.selected_stem)
    if page is None:
        return Selection(None, None, None, None, [], [], {}, None, None, None)

    extraction = _json_for(page.structured_json)
    ocr = _json_for(page.ocr_json)
    error = None if extraction is not None else _json_for(page.error_json)
    facts = facts_by_stem.get(page.stem, [])
    reviews = reviews_by_stem.get(page.stem, {})
    source_file = _source_name(page, ocr)
    links = link_facts(ocr, facts, source_file=source_file, page_number=page.page_number or None)
    fact = next((item for item in facts if item.field_path == st.session_state.selected_field), None)
    link = next((item for item in links if fact and item.field_path == fact.field_path), None)
    entry = reviews.get(fact.field_path) if fact else None
    return Selection(page, extraction, ocr, error, facts, links, reviews, fact, link, entry)


def _header(batch_id: str) -> None:
    title, stages = st.columns([1.15, 3.35 + 1.7], gap="small")
    with title:
        st.markdown(
            f"<p class='wb-kicker'>Migration workbench</p><p class='wb-title'>{html.escape(batch_id)}</p>",
            unsafe_allow_html=True,
        )
    with stages:
        st.radio(
            "Stage",
            STAGES,
            horizontal=True,
            key="stage",
            on_change=_sync_stage,
            label_visibility="collapsed",
        )


def _sync_stage() -> None:
    st.session_state.center_view = STAGE_VIEW[st.session_state.stage]


def _explorer(catalog: BatchCatalog, flags: dict[str, PageFlags]) -> None:
    st.markdown("<p class='wb-kicker wb-pane'>Explorer</p>", unsafe_allow_html=True)
    st.radio("Filter", FILTERS, horizontal=True, key="explorer_filter", label_visibility="collapsed")
    selected_filter = st.session_state.explorer_filter
    if not catalog.packets:
        st.caption("No fax packets in data/01_raw/faxes. Add a PDF there, then split it.")
        st.code("make data-run-raw", language="bash")
        return

    visible = False
    for packet in catalog.packets:
        pages = [page for page in packet.pages if matches_filter(flags[page.stem], selected_filter)]
        if selected_filter != "All" and not pages and packet.pages:
            continue
        if selected_filter not in {"All", "Missing"} and not pages:
            continue
        visible = True
        selected_here = any(page.stem == st.session_state.selected_stem for page in packet.pages)
        with st.expander(packet.filename, expanded=selected_here):
            if not packet.pages:
                st.caption("Not split")
                continue
            if not pages:
                st.caption("No pages match this filter.")
                continue
            for page in pages:
                marker = flags[page.stem].marker
                label = f"{page.page_number:03d}  {marker}" if page.page_number else page.stem
                st.button(
                    label,
                    key=f"page-{page.stem}",
                    use_container_width=True,
                    type="primary" if page.stem == st.session_state.selected_stem else "secondary",
                    on_click=_select_page,
                    args=(page.stem,),
                )
    if not visible:
        st.caption("No pages match this filter.")


def _select_page(stem: str) -> None:
    st.session_state.selected_stem = stem
    st.session_state.selected_field = None
    st.session_state.action_error = None


def _center(selection: Selection, root: Path) -> None:
    st.markdown("<div class='wb-pane wb-center'></div>", unsafe_allow_html=True)
    stage = st.session_state.stage
    page = selection.page
    if page is not None:
        st.markdown(
            f"<p class='wb-meta'>{html.escape(page.stem)} · page {page.page_number or '—'}</p>",
            unsafe_allow_html=True,
        )
    if stage == "Overview":
        _overview(root)
        return
    if stage == "Patient Timeline":
        _patient_timeline(selection)
        return
    if page is None:
        st.caption("Select a page in the explorer.")
        return

    if stage in _VIEWER_STAGES:
        st.radio("Artifact", VIEWS, horizontal=True, key="center_view", label_visibility="collapsed")
    view = st.session_state.center_view
    if view == "Source":
        _source_view(selection)
    elif view == "OCR":
        _ocr_view(selection)
    elif view == "Clinical JSON":
        _json_view(selection, root)
    else:
        _fhir_view(selection, root)


def _patient_timeline(selection: Selection) -> None:
    st.markdown("**Patient timeline**")
    name = _patient_name(selection)
    if not name:
        st.caption("This page has no patient name. Select a page that extracted one.")
        return
    st.caption(name)
    graph = None
    try:
        graph = ClinicalGraph()
        graph.driver.verify_connectivity()
        pages = graph.patient_timeline(name)
    except Exception as exc:
        st.caption(f"Neo4j is not available. {exc}")
        st.code("docker compose up -d && make graph", language="bash")
        return
    finally:
        if graph is not None:
            graph.close()
    if not pages:
        st.caption("No documents for this patient are in the graph yet.")
        st.code("make graph", language="bash")
        return
    for page in pages:
        st.markdown(f"**{html.escape(str(page['document']))}**", unsafe_allow_html=True)
        _timeline_rows("Condition", page["conditions"], ("raw", "display", "code", "status"))
        _timeline_rows("Observation", page["observations"], ("raw", "value", "units", "flag", "code"))
        _timeline_rows("Medication", page["medications"], ("raw", "display", "dosage", "code"))


def _patient_name(selection: Selection) -> str | None:
    extraction = selection.extraction
    if not isinstance(extraction, dict):
        return None
    name = extraction.get("patient_name")
    if not isinstance(name, str):
        return None
    text = name.strip()
    return text or None


def _timeline_rows(kind: str, items: list[dict], columns: tuple[str, ...]) -> None:
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        row = {column: item.get(column) or "" for column in columns}
        if any(row.values()):
            rows.append(row)
    if not rows:
        return
    st.caption(kind)
    _table(rows)


def _overview(root: Path) -> None:
    catalog = load_catalog(root)
    ledger = ReviewLedger(layout_for(root).ledger)
    reviews_by_stem = ledger.by_stem()
    facts_by_stem = {
        page.stem: facts_from_extraction(_json_for(page.structured_json)) for page in catalog.pages()
    }
    counts = summarize(catalog, facts_by_stem, reviews_by_stem)
    st.markdown("**Batch**")
    st.caption("Counts come from files on disk and the review ledger.")
    _table(
        [
            {"measure": "Packets", "count": counts.packets},
            {"measure": "Pages", "count": counts.pages},
            {"measure": "OCR artifacts", "count": counts.ocr},
            {"measure": "Clinical JSON", "count": counts.structured},
            {"measure": "Extraction failures", "count": counts.failures},
            {"measure": "Facts pending review", "count": counts.pending_facts},
            {"measure": "Facts accepted", "count": counts.accepted_facts},
        ]
    )


def _source_view(selection: Selection) -> None:
    page = selection.page
    assert page is not None
    if page.atomic_pdf is None:
        st.caption("This page has not been split.")
        st.code("make triage-pdfs", language="bash")
        return
    frame = source_frame(selection.ocr)
    origin = frame[0] if frame else (0.0, 0.0)
    source_size = frame[1] if frame else None
    highlight = selection.link.bbox if selection.link and selection.link.resolved else None
    try:
        png = _cached_png(
            str(page.atomic_pdf),
            page.atomic_pdf.stat().st_mtime_ns,
            highlight,
            origin,
            source_size,
        )
    except Exception as exc:
        st.caption(f"Could not render this page ({type(exc).__name__}).")
        return
    st.image(png, use_container_width=True)
    link = selection.link
    if link and link.resolved:
        order = f" · reading order {link.reading_order}" if link.reading_order is not None else ""
        st.caption(f"{link.source_file} · page {link.page_number} · block {link.block_index}{order}")
        if highlight is None or source_size is None:
            st.caption("The value is in an OCR block, but the box could not be placed on the page.")
    elif selection.fact is not None:
        st.caption("Provenance is unresolved. No OCR block contains this value.")


def _ocr_view(selection: Selection) -> None:
    page = selection.page
    assert page is not None
    if selection.ocr is None:
        st.caption("OCR has not been run for this page.")
        st.code("make ocr", language="bash")
        return
    blocks = selection.ocr.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        parsed = _parsed_text(page)
        st.code(parsed or "OCR file has no blocks.", language=None)
        return
    matched = selection.link.block_index if selection.link and selection.link.resolved else None
    indexed = [(index, block) for index, block in enumerate(blocks) if isinstance(block, dict)]
    indexed.sort(key=lambda item: item[1].get("reading_order", 9999))
    parts: list[str] = []
    for index, block in indexed:
        text = _plain_block(block)
        if not text:
            continue
        label = f"block {index}"
        if index == matched:
            label += " · matched"
        parts.append(f"{label}\n{text}")
    if parts:
        st.code("\n\n".join(parts), language=None)
    else:
        parsed = _parsed_text(page)
        st.code(parsed or "OCR file has no text.", language=None)


def _json_view(selection: Selection, root: Path) -> None:
    page = selection.page
    assert page is not None
    if selection.extraction is not None and page.structured_json is not None:
        st.caption(_rel(page.structured_json, root))
        st.code(json.dumps(selection.extraction, indent=2), language="json")
        return
    if selection.error is not None:
        st.caption("Extraction failed for this page.")
        st.code(json.dumps(selection.error, indent=2), language="json")
        return
    st.caption("Extraction has not been run for this page.")
    st.code("make extract", language="bash")


def _fhir_view(selection: Selection, root: Path) -> None:
    page = selection.page
    assert page is not None
    path = layout_for(root).fhir / f"{page.stem}.json"
    bundle = _json_for(path)
    if not isinstance(bundle, dict):
        st.caption("FHIR serialization has not been run for this page.")
        st.code("make fhir", language="bash")
        return
    entries = bundle.get("entry")
    count = len(entries) if isinstance(entries, list) else 0
    kinds = []
    if isinstance(entries, list):
        for item in entries:
            resource = item.get("resource") if isinstance(item, dict) else None
            if isinstance(resource, dict) and isinstance(resource.get("resourceType"), str):
                kinds.append(resource["resourceType"])
    summary = ", ".join(f"{kinds.count(kind)} {kind}" for kind in dict.fromkeys(kinds))
    st.caption(f"{_rel(path, root)} · {bundle.get('type', 'bundle')} · {count} resources")
    if summary:
        st.caption(summary)
    st.code(json.dumps(bundle, indent=2), language="json")


def _inspector(selection: Selection, ledger: ReviewLedger) -> bool:
    """Draw the inspector. Return True when a review was written and the app should reload."""
    st.markdown("<p class='wb-kicker wb-pane'>Inspector</p>", unsafe_allow_html=True)
    page = selection.page
    if page is None:
        st.caption("No page selected.")
        return False
    if selection.extraction is None:
        rows = _check_rows(page, None, None, None)
        _draw_checks(rows)
        if selection.error is not None:
            st.caption(f"{selection.error.get('error_type', 'failed')} · {selection.error.get('attempts', 0)} attempts")
            message = selection.error.get("message")
            if isinstance(message, str) and message:
                st.text(message)
        else:
            st.caption("Schema validation has not run for this page.")
            st.code("make extract", language="bash")
        return False

    if not selection.facts:
        rows = _check_rows(page, None, None, None)
        _draw_checks(rows)
        st.caption("No demographics, conditions, medications, or lab observations were extracted.")
        return False

    for fact in selection.facts:
        st.button(
            _fact_label(fact),
            key=f"fact-{page.stem}-{fact.field_path}",
            use_container_width=True,
            type="primary" if selection.fact and selection.fact.field_path == fact.field_path else "secondary",
            on_click=_select_fact,
            args=(fact.field_path,),
        )

    fact = selection.fact
    if fact is None:
        st.caption("Select a record to inspect provenance and review it.")
        return False

    entry = selection.entry
    st.caption(fact.kind)
    st.code(fact.value, language=None)
    if entry and entry.status == "corrected" and entry.revised_value:
        st.caption("Revised")
        st.code(entry.revised_value, language=None)
    if fact.dosage:
        st.caption(f"Dosage {fact.dosage}")
    if fact.result:
        result = f"{fact.result} {fact.units}".strip() if fact.units else fact.result
        st.caption(f"Result {result}")
    if fact.flag:
        st.caption(f"Flag {fact.flag}")
    if fact.clinical_status:
        st.caption(f"Clinical status {fact.clinical_status}")
    if entry and entry.code:
        st.caption("Code")
        st.code(f"{entry.code_system}  {entry.code}  {entry.display or ''}".strip(), language=None)
    if entry and entry.reason:
        st.caption(entry.reason)
    if entry:
        st.caption(f"{entry.status} · {entry.timestamp}")

    link = selection.link
    st.markdown("**Provenance**")
    if link and link.resolved:
        st.caption(f"{link.source_file} · page {link.page_number} · block {link.block_index}")
        if link.block_text:
            st.text(link.block_text)
        if link.confidence is not None:
            st.caption(f"OCR confidence {link.confidence:.2f}")
    else:
        st.caption("Provenance is unresolved. No OCR block contains this value.")

    if fact.requires_code and fact_needs_code(entry):
        st.caption("This value has no terminology code. It stays out of the FHIR preview until you attach a code and accept it.")

    rows = _check_rows(page, fact, link, entry)
    _draw_checks(rows)
    wrote = _review_form(selection, ledger)
    if not wrote and st.session_state.action_error:
        st.caption(st.session_state.action_error)
    return wrote


def fact_needs_code(entry: ReviewEntry | None) -> bool:
    if entry is not None and entry.status == "rejected":
        return False
    return entry is None or not (entry.code and entry.code_system and entry.status in {"accepted", "corrected"})


def _review_form(selection: Selection, ledger: ReviewLedger) -> bool:
    fact = selection.fact
    page = selection.page
    assert fact is not None and page is not None
    with st.form(f"review-{page.stem}-{fact.field_path}"):
        revised = st.text_input("Revised value", value=effective_value(fact.value, selection.entry))
        reason = st.text_input("Reason")
        system = code = display = ""
        if fact.requires_code:
            system = st.text_input("Code system", placeholder=_code_system_placeholder(fact.kind))
            code = st.text_input("Code")
            display = st.text_input("Display")
        accept, reject, correct = st.columns(3)
        accepted = accept.form_submit_button("Accept", use_container_width=True)
        rejected = reject.form_submit_button("Reject", use_container_width=True)
        corrected = correct.form_submit_button("Correct", use_container_width=True)

    if not (accepted or rejected or corrected):
        return False
    error = _validate_action(fact, accepted, rejected, corrected, revised, reason, system, code, display)
    if error:
        st.session_state.action_error = error
        return False
    status = "accepted" if accepted else "rejected" if rejected else "corrected"
    try:
        ledger.record(
            stem=page.stem,
            field_path=fact.field_path,
            status=status,
            original_value=fact.value,
            revised_value=revised if corrected else None,
            code_system=system if fact.requires_code and (accepted or corrected) else None,
            code=code if fact.requires_code and (accepted or corrected) else None,
            display=display if fact.requires_code and (accepted or corrected) else None,
            reason=reason or None,
        )
    except ValueError as exc:
        st.session_state.action_error = str(exc)
        return False
    st.session_state.action_error = None
    return True


def _validate_action(
    fact: Fact,
    accepted: bool,
    rejected: bool,
    corrected: bool,
    revised: str,
    reason: str,
    system: str,
    code: str,
    display: str,
) -> str | None:
    reason_text = reason.strip()
    revised_text = revised.strip()
    system_text, code_text, display_text = system.strip(), code.strip(), display.strip()
    if rejected and not reason_text:
        return "A rejection needs a reason."
    if corrected and (not revised_text or not reason_text):
        return "A correction needs a revised value and a reason."
    coded = bool(system_text or code_text or display_text)
    if fact.requires_code and accepted and not (system_text and code_text and display_text):
        return "This record needs a code system, code, and display before it can be accepted."
    if corrected and coded and not (system_text and code_text and display_text):
        return "A code needs a system, code, and display."
    return None


def _select_fact(field_path: str) -> None:
    st.session_state.selected_field = field_path
    st.session_state.action_error = None
    if st.session_state.stage in {"Overview", "Patient Timeline"}:
        st.session_state.stage = "OCR"
    st.session_state.center_view = "Source"


def _console(
    catalog: BatchCatalog,
    ledger: ReviewLedger,
    reviews_by_stem: dict[str, dict[str, ReviewEntry]],
) -> None:
    with st.expander("Pipeline console", expanded=False):
        rows = []
        failures = []
        for page in catalog.pages():
            error = _json_for(page.error_json) if page.structured_json is None else None
            error_type = error.get("error_type") if isinstance(error, dict) else None
            rows.append(
                {
                    "page": page.stem,
                    "ocr": "yes" if page.ocr_json else "no",
                    "structured": "yes" if page.structured_json else "no",
                    "failure": error_type or "",
                    "reviews": len(reviews_by_stem.get(page.stem, {})),
                }
            )
            if isinstance(error, dict):
                failures.append(
                    {
                        "page": page.stem,
                        "type": error.get("error_type", ""),
                        "attempts": error.get("attempts", ""),
                        "message": error.get("message", ""),
                    }
                )
        st.caption("Stage coverage")
        if rows:
            _table(rows, height=220)
        else:
            st.caption("No pages yet.")
        st.caption("Extraction failures")
        if failures:
            _table(failures, height=180)
        else:
            st.caption("No extraction failures.")
        st.caption("Review ledger")
        events = [
            {
                "time": entry.timestamp,
                "page": entry.stem,
                "field": entry.field_path,
                "status": entry.status,
            }
            for entry in ledger.entries()[-30:]
        ]
        if events:
            _table(events, height=180)
        else:
            st.caption("No review actions yet.")


def _check_rows(
    page: PageArtifacts,
    fact: Fact | None,
    link: ProvenanceLink | None,
    entry: ReviewEntry | None,
) -> list[tuple[str, str]]:
    if page.structured_json is not None:
        schema = "Passed"
    elif page.error_json is not None:
        schema = "Failed"
    else:
        schema = "Pending"
    if fact is None:
        return [("Schema", schema), ("Terminology", "Pending"), ("Provenance", "Pending")]
    if not fact.requires_code:
        terminology = "Not required"
    elif entry and entry.status == "rejected":
        terminology = "Rejected"
    elif entry and entry.status in {"accepted", "corrected"} and entry.code and entry.code_system:
        terminology = "Passed"
    else:
        terminology = "Review"
    provenance = "Linked" if link and link.resolved else "Unresolved"
    return [("Schema", schema), ("Terminology", terminology), ("Provenance", provenance)]


def _draw_checks(rows: list[tuple[str, str]]) -> None:
    open_count = sum(1 for _, state in rows if state in _OPEN)
    st.caption(f"{len(rows)} checks · {open_count} open")
    for label, state in rows:
        css = _STATE_CLASS.get(state, "wb-muted")
        st.markdown(
            "<div class='wb-check'>"
            f"<span>{html.escape(label)}</span>"
            f"<span class='{css}'>{html.escape(state)}</span>"
            "</div>",
            unsafe_allow_html=True,
        )


def _table(rows: list[dict], height: int | None = None) -> None:
    """HTML table so the grid stays black on white. The dataframe canvas ignores CSS."""
    if not rows:
        return
    columns = list(rows[0])
    head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(row.get(column, '')))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    style = f" style='max-height:{height}px'" if height else ""
    st.markdown(
        f"<div class='wb-table'{style}><table><thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _fact_label(fact: Fact) -> str:
    shown = fact.value
    if fact.kind == "Observation" and fact.result:
        shown = " ".join(part for part in (fact.value, fact.result, fact.units, fact.flag) if part)
    if len(shown) > 72:
        shown = shown[:69] + "..."
    return f"{fact.kind}  {shown}"


def _code_system_placeholder(kind: str) -> str:
    if kind == "Medication":
        return "http://www.nlm.nih.gov/research/umls/rxnorm"
    if kind == "Observation":
        return "http://loinc.org"
    return "http://snomed.info/sct"


def _source_name(page: PageArtifacts, ocr: dict | None) -> str | None:
    if isinstance(ocr, dict) and isinstance(ocr.get("source"), str) and ocr["source"].strip():
        return ocr["source"].strip()
    if page.atomic_pdf is not None:
        return page.atomic_pdf.name
    return None


def _find_page(catalog: BatchCatalog, stem: str | None) -> PageArtifacts | None:
    if stem is None:
        return None
    return next((page for page in catalog.pages() if page.stem == stem), None)


def _plain_block(block: dict) -> str:
    from ehr_migration_engine.vision.spatial_parser import clean_html_to_text

    html_text = block.get("html")
    if isinstance(html_text, str) and html_text.strip():
        return clean_html_to_text(html_text)
    return ""


def _parsed_text(page: PageArtifacts) -> str:
    if page.parsed_text is None or not page.parsed_text.is_file():
        return ""
    return page.parsed_text.read_text(encoding="utf-8")


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _json_for(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    return _cached_json(str(path), path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def _cached_json(path: str, mtime_ns: int) -> dict | None:
    del mtime_ns
    data = read_json(Path(path))
    return data if isinstance(data, dict) else None


@st.cache_data(show_spinner=False)
def _cached_png(
    path: str,
    mtime_ns: int,
    highlight: tuple[float, float, float, float] | None,
    origin: tuple[float, float],
    source_size: tuple[float, float] | None,
) -> bytes:
    del mtime_ns
    return render_page_png(Path(path), highlight, origin=origin, source_size=source_size)


if __name__ == "__main__":
    main()
