"""Fetch CMS / ONC interoperability certification test documents.

Pulls the public ONC 2015 Edition C-CDA test-data PDFs used for Transitions of
Care (inpatient + ambulatory). These instruction / sample packets are the
legacy unstructured surfaces EHR vendors must ingest alongside FHIR and C-CDA.
"""

from __future__ import annotations

import argparse
from typing import Any
from urllib.parse import quote

from common import ROOT, download_file, group_dir, stage_into_faxes, write_manifest

GROUP = "03_cms_onc"

REPO = "onc-healthit/2015-certification-ccda-testdata"
BRANCH = "master"
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"

# Prefer latest inpatient ToC / discharge-oriented instruction PDFs, plus a
# couple of ambulatory counterparts for layout diversity.
SAMPLES: list[dict[str, str]] = [
    {
        "name": "onc_toc_inp_sample1_v14",
        "path": (
            "Sender SUT Test Data/170.315_b1_ToC_Inp/"
            "170.315_b1_toc_inp_sample1_v14.pdf"
        ),
    },
    {
        "name": "onc_toc_inp_sample2_v14",
        "path": (
            "Sender SUT Test Data/170.315_b1_ToC_Inp/"
            "170.315_b1_toc_inp_sample2_v14.pdf"
        ),
    },
    {
        "name": "onc_toc_amb_sample1_v14",
        "path": (
            "Sender SUT Test Data/170.315_b1_ToC_Amb/"
            "170.315_b1_toc_amb_sample1_v14.pdf"
        ),
    },
    {
        "name": "onc_toc_amb_sample2_v14",
        "path": (
            "Sender SUT Test Data/170.315_b1_ToC_Amb/"
            "170.315_b1_toc_amb_sample2_v14.pdf"
        ),
    },
    {
        "name": "onc_ciri_inp_discharge_summary_v7",
        "path": (
            "Sender SUT Test Data/170.315_b2_CIRI_Inp/"
            "170.315_b2_ciri__r21_sample1_ds_v7.pdf"
        ),
    },
    {
        "name": "onc_ciri_inp_referral_note_v7",
        "path": (
            "Sender SUT Test Data/170.315_b2_CIRI_Inp/"
            "170.315_b2_ciri__r21_sample1_rn_v7.pdf"
        ),
    },
    {
        "name": "onc_ccds_inp_sample1_v14",
        "path": (
            "Sender SUT Test Data/170.315_b4_CCDS_Inp/"
            "170.315_b4_ccds_create_inp_sample1_v14.pdf"
        ),
    },
    {
        "name": "onc_de_inp_sample1_v14",
        "path": (
            "Sender SUT Test Data/170.315_b6_DE_Inp/"
            "170.315_b6_de_inp_sample1_v14.pdf"
        ),
    },
]


def raw_url(repo_path: str) -> str:
    return f"{RAW}/{quote(repo_path)}"


def fetch(*, limit: int, stage: int) -> None:
    out = group_dir(GROUP)
    selected = SAMPLES[: max(limit, 0)]
    saved: list[dict[str, Any]] = []
    paths = []

    for sample in selected:
        dest = out / f"{sample['name']}.pdf"
        url = raw_url(sample["path"])
        ok = download_file(url, dest)
        if not ok:
            continue
        paths.append(dest)
        saved.append(
            {
                "name": sample["name"],
                "repo_path": sample["path"],
                "url": url,
                "path": str(dest.relative_to(ROOT)),
            }
        )

    write_manifest(
        out / "manifest.json",
        {
            "group": GROUP,
            "source": f"GitHub {REPO} ({BRANCH})",
            "upstream": "https://www.healthit.gov/test-method/transitions-care/",
            "count": len(saved),
            "documents": saved,
        },
    )

    if stage > 0 and paths:
        stage_into_faxes(paths[:stage], prefix="cms")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=len(SAMPLES), help="Max PDFs")
    parser.add_argument(
        "--stage",
        type=int,
        default=2,
        help="Copy this many into data/01_raw/faxes (0 to skip)",
    )
    args = parser.parse_args()
    fetch(limit=args.limit, stage=args.stage)


if __name__ == "__main__":
    main()
