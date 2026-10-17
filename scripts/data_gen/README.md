# Raw data generators

These scripts fill `data/01_raw/` at the project root. Output paths are resolved from each script file, so the files land in the same place whether you use `make` or run a script from another directory.

`data/01_raw/` is committed so other people can clone the corpus. Later pipeline stages stay gitignored.

## What lands where

```
data/01_raw/
├── synthea/          # structured charts: fhir/, csv/, ccda/
├── mtsamples/
│   ├── clinical_notes_full.csv
│   └── text_files/   # first 20 notes, one file each
└── faxes/            # 5 skewed, noisy, thresholded PDFs
```

| Generator | Writes | Needs |
| --- | --- | --- |
| `run_synthea.sh` | `data/01_raw/synthea/` | Java, `curl` |
| `fetch_mtsamples.py` | `data/01_raw/mtsamples/` | network access to Hugging Face |
| `dirty_fax_gen.py` | `data/01_raw/faxes/` | the text files from the MTSamples fetch |

## Commands

From the project root:

```bash
make data-synthea      # 10 synthetic patients, seed 12345
make data-mtsamples    # full note table, plus 20 plain-text charts
make data-faxes        # 5 scanned-style PDFs
make data-notes        # notes, then faxes
make data-raw          # all of the above, in that order
```

`make data-faxes` expects `data/01_raw/mtsamples/text_files/` to already exist. `make data-notes` runs the fetch first.

The same scripts can be called directly:

```bash
./scripts/data_gen/run_synthea.sh
uv run python scripts/data_gen/fetch_mtsamples.py
uv run python scripts/data_gen/dirty_fax_gen.py
```

## What each generator does

**Synthea** downloads `synthea-with-dependencies.jar` next to the shell script (gitignored) and generates 10 patients. FHIR, CSV, and CCDA all go under `data/01_raw/synthea/`.

**MTSamples** downloads [`harishnair04/mtsamples`](https://huggingface.co/datasets/harishnair04/mtsamples), the public MTSamples transcription table (about 5,000 notes). The full table is saved as CSV. The first 20 rows are also written as individual text files so later stages can ingest one chart at a time.

**Dirty fax** reads those text files, draws each note on a white page, then skews it, adds blur and noise, and thresholds it to black and white. The first 5 notes are saved as PDFs in `data/01_raw/faxes/`. That is the unstructured input the OCR stage is meant to read.
