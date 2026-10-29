# Real-world OCR stress corpus

Public, legally cleared born-analog / corporate-layout PDFs for stressing Surya
and the spatial parser. Synthetic generators stay under `scripts/data_gen/`;
these scripts pull genuine adversarial layouts.

Downloads land in `data/reference/real_world/<group>/`. A few samples are also
staged into the live OCR drop `data/01_raw/faxes/` (use `--stage 0` to skip).

## Groups

| Script | Group dir | What it pulls |
| --- | --- | --- |
| `fetch_01_ucsf_tobacco.py` | `01_ucsf_tobacco/` | Degraded medical charts, discharge summaries, lab reports from the UCSF Truth Tobacco Industry Documents (public IDL dataset PDFs) |
| `fetch_02_pathology_labs.py` | `02_pathology_labs/` | Sample reports from Lal PathLabs, Quest, Labcorp, plus Sterling Accuris (India nested-table / watermark class) |
| `fetch_03_cms_onc.py` | `03_cms_onc/` | ONC 2015 Edition Transitions of Care / CCDS instruction PDFs used in EHR certification |

## Commands

From the project root:

```bash
make data-ucsf          # adversarial litigation scans
make data-pathlabs      # corporate pathology sample reports
make data-cms-onc       # CMS/ONC certification test PDFs
make data-real          # all three, in order
```

Or call a script directly:

```bash
uv run python scripts/real_world/fetch_01_ucsf_tobacco.py --limit 8 --stage 3
uv run python scripts/real_world/fetch_02_pathology_labs.py --stage 3
uv run python scripts/real_world/fetch_03_cms_onc.py --stage 2
```

Then triage and OCR:

```bash
make data-run-raw
make ocr
```

## Notes

- **UCSF IDL**: Solr search is public; PDFs come from
  `ucsf-idl-dataset.s3.us-east-1.amazonaws.com/{id[0]}/{id[1]}/{id[2]}/{id[3]}/{id}/{id}.pdf`.
  Only `availability: public` docs are kept.
- **Metropolis India**: no stable public sample-report PDF was found. Sterling
  Accuris covers that watermark / nested-table class; Lal PathLabs covers the
  other major India chain in the dork list.
- **CMS/ONC**: PDFs are instruction / test-procedure packets from
  `onc-healthit/2015-certification-ccda-testdata`, not live PHI.
