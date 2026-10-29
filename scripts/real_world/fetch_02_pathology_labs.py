"""Fetch public sample report PDFs from major diagnostic / pathology chains.

Corporate lab reports stress nested tables, accreditation logos, and
anti-forgery watermarks — the layout class that breaks naive Markdown rebuilds.

Sources (public sample / marketing PDFs only):
  - Dr Lal PathLabs (cdn1.lalpathlabs.com live sample reports)
  - Quest Diagnostics (specimen / sample report PDFs)
  - Labcorp (test-menu sample reports)
  - Sterling Accuris (public unlocked sample; Metropolis-class Indian layout)

Metropolis Healthcare does not currently host a stable public sample-report PDF;
Sterling Accuris covers that nested-table / watermark class for the India set.
"""

from __future__ import annotations

import argparse
from typing import Any

from common import ROOT, download_file, group_dir, stage_into_faxes, write_manifest

GROUP = "02_pathology_labs"

# Curated, direct PDF URLs (verified public sample reports).
SAMPLES: list[dict[str, str]] = [
    # --- Dr Lal PathLabs ---
    {
        "lab": "lalpathlabs",
        "name": "lal_liver_panel_Z005",
        "url": "https://cdn1.lalpathlabs.com/live/reports/Z005.pdf",
    },
    {
        "lab": "lalpathlabs",
        "name": "lal_kidney_panel_Z007",
        "url": "https://cdn1.lalpathlabs.com/live/reports/Z007.pdf",
    },
    {
        "lab": "lalpathlabs",
        "name": "lal_cmv_pcr_N031",
        "url": "https://cdn1.lalpathlabs.com/live/reports/N031.pdf",
    },
    {
        "lab": "lalpathlabs",
        "name": "lal_allergy_comprehensive_Z089",
        "url": "https://cdn1.lalpathlabs.com/live/reports/Z089.pdf",
    },
    {
        "lab": "lalpathlabs",
        "name": "lal_sample_Z003",
        "url": "https://cdn1.lalpathlabs.com/live/reports/Z003.pdf",
    },
    {
        "lab": "lalpathlabs",
        "name": "lal_sample_Z010",
        "url": "https://cdn1.lalpathlabs.com/live/reports/Z010.pdf",
    },
    {
        "lab": "lalpathlabs",
        "name": "lal_sample_H001",
        "url": "https://cdn1.lalpathlabs.com/live/reports/H001.pdf",
    },
    # --- Quest Diagnostics ---
    {
        "lab": "questdiagnostics",
        "name": "quest_vit_d_in_range",
        "url": (
            "https://www.questdiagnostics.com/content/dam/corporate/restricted/"
            "documents/test-directory/vit-d-db066889v-in-range.pdf"
        ),
    },
    {
        "lab": "questdiagnostics",
        "name": "quest_vit_d_out_of_range",
        "url": (
            "https://www.questdiagnostics.com/content/dam/corporate/restricted/"
            "documents/test-directory/vit-d-db066890v-out-of-range.pdf"
        ),
    },
    {
        "lab": "questdiagnostics",
        "name": "quest_diabetes_risk_panel",
        "url": (
            "https://www.questdiagnostics.com/content/dam/corporate/unrestricted/"
            "documents/other/drpws_sample_report/DRPwS_sample_report.pdf"
        ),
    },
    # --- Labcorp ---
    {
        "lab": "labcorp",
        "name": "labcorp_sample_180025",
        "url": "https://files.labcorp.com/testmenu-d8/sample_reports/180025.pdf",
    },
    {
        "lab": "labcorp",
        "name": "labcorp_sample_006530",
        "url": "https://files.labcorp.com/testmenu-d8/sample_reports/006530.pdf",
    },
    {
        "lab": "labcorp",
        "name": "labcorp_sample_322777",
        "url": "https://files.labcorp.com/testmenu-d8/sample_reports/322777.pdf",
    },
    {
        "lab": "labcorp",
        "name": "labcorp_sample_001453",
        "url": "https://files.labcorp.com/testmenu-d8/sample_reports/001453.pdf",
    },
    {
        "lab": "labcorp",
        "name": "labcorp_sars_spike_ab_164090",
        "url": "https://files.labcorp.com/testmenu-d8/sample_reports/164090.pdf",
    },
    # --- Sterling Accuris (India nested-table / watermark class) ---
    {
        "lab": "sterling_accuris",
        "name": "sterling_accuris_pathology_sample",
        "url": (
            "https://sterlingaccuris.com/static-assets/pdfs/"
            "sterling-accuris-pathology-sample-report-unlocked.pdf"
        ),
    },
]

# Preferred labs to stage into the live fax drop for a quick `make ocr` pass.
STAGE_PRIORITY = (
    "sterling_accuris_pathology_sample",
    "labcorp_sample_180025",
    "lal_kidney_panel_Z007",
    "quest_diabetes_risk_panel",
    "labcorp_sample_006530",
)


def fetch(*, labs: set[str] | None, stage: int, include_sterling: bool) -> None:
    out = group_dir(GROUP)
    selected = [
        sample
        for sample in SAMPLES
        if (labs is None or sample["lab"] in labs)
        and (include_sterling or sample["lab"] != "sterling_accuris")
    ]
    if not selected:
        raise SystemExit("No pathology samples matched the requested filters.")

    saved: list[dict[str, Any]] = []
    by_name: dict[str, Any] = {}
    for sample in selected:
        dest = out / f"{sample['name']}.pdf"
        ok = download_file(sample["url"], dest)
        if not ok:
            continue
        record = {
            "lab": sample["lab"],
            "name": sample["name"],
            "url": sample["url"],
            "path": str(dest.relative_to(ROOT)),
        }
        saved.append(record)
        by_name[sample["name"]] = dest

    write_manifest(
        out / "manifest.json",
        {
            "group": GROUP,
            "source": "Public diagnostic-chain sample report PDFs",
            "notes": (
                "Metropolis India does not publish a stable public sample-report PDF; "
                "Sterling Accuris is included as the India nested-table / watermark stand-in."
            ),
            "dork_hints": [
                'filetype:pdf site:lalpathlabs.com "sample report"',
                'filetype:pdf site:metropolisindia.com "test report"',
                'filetype:pdf site:questdiagnostics.com "specimen report"',
                'filetype:pdf site:labcorp.com "sample"',
            ],
            "count": len(saved),
            "documents": saved,
        },
    )

    if stage <= 0:
        return
    ordered = [by_name[name] for name in STAGE_PRIORITY if name in by_name]
    # Fall back to whatever downloaded if priority list missed.
    if len(ordered) < stage:
        for dest in by_name.values():
            if dest not in ordered:
                ordered.append(dest)
            if len(ordered) >= stage:
                break
    stage_into_faxes(ordered[:stage], prefix="pathlab")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lab",
        action="append",
        dest="labs",
        choices=sorted({s["lab"] for s in SAMPLES}),
        help="Limit to one or more lab keys (repeatable)",
    )
    parser.add_argument(
        "--stage",
        type=int,
        default=3,
        help="Copy this many into data/01_raw/faxes (0 to skip)",
    )
    parser.add_argument(
        "--no-sterling",
        action="store_true",
        help="Skip the Sterling Accuris India sample",
    )
    args = parser.parse_args()
    labs = set(args.labs) if args.labs else None
    fetch(labs=labs, stage=args.stage, include_sterling=not args.no_sterling)


if __name__ == "__main__":
    main()
