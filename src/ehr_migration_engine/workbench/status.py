"""Page and batch status derived from artifacts and the review ledger."""

from dataclasses import dataclass

from .catalog import BatchCatalog, PageArtifacts
from .facts import Fact
from .review import ReviewEntry


@dataclass(frozen=True)
class PageFlags:
    missing: bool
    pending: bool
    reviewed: bool
    failed: bool

    @property
    def marker(self) -> str:
        if self.failed:
            return "failed"
        if self.missing:
            return "missing"
        if self.pending:
            return "pending"
        if self.reviewed:
            return "reviewed"
        return "missing"


@dataclass(frozen=True)
class BatchCounts:
    packets: int
    pages: int
    ocr: int
    structured: int
    failures: int
    pending_facts: int
    accepted_facts: int


def fact_bucket(fact: Fact, entry: ReviewEntry | None) -> str:
    """pending, rejected, or accepted. Accepted still requires a code when the fact needs one."""
    if entry is None or entry.status == "pending_review":
        return "pending"
    if entry.status == "rejected":
        return "rejected"
    if entry.status in {"accepted", "corrected"}:
        if fact.requires_code and not (entry.code and entry.code_system):
            return "pending"
        return "accepted"
    return "pending"


def page_flags(page: PageArtifacts, facts: list[Fact], reviews: dict[str, ReviewEntry]) -> PageFlags:
    failed = page.error_json is not None and page.structured_json is None
    missing = page.atomic_pdf is None or page.ocr_json is None or page.structured_json is None
    pending = False
    reviewed = False
    if page.structured_json is not None:
        if not facts:
            pending = True
        for fact in facts:
            bucket = fact_bucket(fact, reviews.get(fact.field_path))
            entry = reviews.get(fact.field_path)
            if entry is not None and entry.status != "pending_review":
                reviewed = True
            if bucket == "pending":
                pending = True
    return PageFlags(missing=missing, pending=pending, reviewed=reviewed, failed=failed)


def matches_filter(flags: PageFlags, selected: str) -> bool:
    if selected == "All":
        return True
    if selected == "Missing":
        return flags.missing or flags.failed
    if selected == "Pending":
        return flags.pending
    if selected == "Reviewed":
        return flags.reviewed
    return True


def summarize(
    catalog: BatchCatalog,
    facts_by_stem: dict[str, list[Fact]],
    reviews_by_stem: dict[str, dict[str, ReviewEntry]],
) -> BatchCounts:
    pages = catalog.pages()
    pending_facts = 0
    accepted_facts = 0
    for page in pages:
        if page.structured_json is None:
            continue
        reviews = reviews_by_stem.get(page.stem, {})
        for fact in facts_by_stem.get(page.stem, []):
            bucket = fact_bucket(fact, reviews.get(fact.field_path))
            if bucket == "accepted":
                accepted_facts += 1
            elif bucket == "pending":
                pending_facts += 1
    return BatchCounts(
        packets=len(catalog.packets),
        pages=len(pages),
        ocr=sum(1 for page in pages if page.ocr_json is not None),
        structured=sum(1 for page in pages if page.structured_json is not None),
        failures=sum(1 for page in pages if page.error_json is not None and page.structured_json is None),
        pending_facts=pending_facts,
        accepted_facts=accepted_facts,
    )
