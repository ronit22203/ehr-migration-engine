# Raw data generators

These scripts fill `data/01_raw/` at the project root. Output paths are resolved from each script file, so the files land in the same place whether you use `make` or run a script from another directory.

`data/01_raw/` is committed so other people can clone the corpus. Later pipeline stages stay gitignored.

## What lands where

```
data/01_raw/
├── synthea/          # structured charts: fhir/, csv/, ccda/
├── mtsamples/
│   ├── clinical_notes_full.csv
│   └── text_files/   # 24 long notes, one file each
└── faxes/            # 8 multi-page scanned fax packets
```

| Generator | Writes | Needs |
| --- | --- | --- |
| `run_synthea.sh` | `data/01_raw/synthea/` | Java, `curl` |
| `fetch_mtsamples.py` | `data/01_raw/mtsamples/` | network access to Hugging Face |
| `dirty_fax_gen.py` | `data/01_raw/faxes/` | the 24 text files from the MTSamples fetch |

## Commands

From the project root:

```bash
make data-synthea      # 10 synthetic patients, seed 12345
make data-mtsamples    # full note table, plus 24 long plain-text charts
make data-faxes        # 8 multi-page scanned fax packets
make data-notes        # notes, then faxes
make data-raw          # all of the above, in that order
make data-run-raw      # copy fax packets into triage and split each page
```

`make data-faxes` expects `data/01_raw/mtsamples/text_files/` to already exist. `make data-notes` runs the fetch first. `make data-run-raw` expects the packet PDFs in `data/01_raw/faxes/` and writes one file per page under `data/02_triage/atomic_pages/`.

The same scripts can be called directly:

```bash
./scripts/data_gen/run_synthea.sh
uv run python scripts/data_gen/fetch_mtsamples.py
uv run python scripts/data_gen/dirty_fax_gen.py
```

## What each generator does

**Synthea** downloads `synthea-with-dependencies.jar` next to the shell script (gitignored) and generates 10 patients. FHIR, CSV, and CCDA all go under `data/01_raw/synthea/`.

**MTSamples** downloads [`harishnair04/mtsamples`](https://huggingface.co/datasets/harishnair04/mtsamples), the public MTSamples transcription table (about 5,000 notes). The full table is saved as CSV. Twenty-four long notes, spread across specialties and at least 4,000 characters each, are also written as individual text files.

**Dirty fax** groups those notes into 8 packets of 3. Each PDF has a cover page, the notes flowing across as many pages as they need, and a laboratory table. Every page is skewed, grained, and thresholded. Packets are saved as `packet_001_scanned.pdf` through `packet_008_scanned.pdf` in `data/01_raw/faxes/`. That is the unstructured input the OCR stage is meant to read. Splitting a packet into single pages is a later triage step, not part of this generator.
