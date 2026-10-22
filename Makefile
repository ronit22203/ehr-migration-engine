.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
UV   := uv run --project $(ROOT) python

.PHONY: help data-synthea data-mtsamples data-faxes data-notes data-raw data-run-raw triage-pdfs ocr parse extract workbench

help:
	@printf '%s\n' \
		'Live documents land in data/01_raw/faxes.' \
		'Synthetic generators write to data/reference/synthetic and do not touch that drop.' \
		'' \
		'  make data-synthea     10 Synthea patients into data/reference/synthetic/synthea' \
		'  make data-mtsamples   MTSamples notes into data/reference/synthetic/mtsamples' \
		'  make data-faxes       8 fax packets into data/reference/synthetic/faxes' \
		'  make data-notes       notes, then faxes' \
		'  make data-raw         all three generators, in order' \
		'' \
		'  make data-run-raw     copy data/01_raw/faxes into triage and split each page' \
		'  make triage-pdfs      split data/02_triage/unstructured into single pages' \
		'  make ocr              Surya OCR on atomic pages into data/03_ocr' \
		'  make parse            rebuild OCR JSON into reading-order plain text' \
		'  make extract          extract clinical JSON from parsed notes via Ollama' \
		'  make workbench        open the clinical migration workbench'

data-synthea:
	$(ROOT)/scripts/data_gen/run_synthea.sh

data-mtsamples:
	$(UV) $(ROOT)/scripts/data_gen/fetch_mtsamples.py

data-faxes:
	$(UV) $(ROOT)/scripts/data_gen/dirty_fax_gen.py

data-notes: data-mtsamples data-faxes

data-raw: data-synthea data-notes

data-run-raw:
	rm -rf $(ROOT)/data/02_triage/unstructured $(ROOT)/data/02_triage/atomic_pages
	mkdir -p $(ROOT)/data/02_triage/unstructured
	cp $(ROOT)/data/01_raw/faxes/*.pdf $(ROOT)/data/02_triage/unstructured/
	$(UV) -m ehr_migration_engine.ingestion.pdf_handler

triage-pdfs:
	$(UV) -m ehr_migration_engine.ingestion.pdf_handler

ocr:
	PYTHONUNBUFFERED=1 LOGLEVEL=DEBUG $(UV) -m ehr_migration_engine.vision.surya_client

parse:
	uv run python -m src.ehr_migration_engine.vision.spatial_parser

extract:
	uv run python -m src.ehr_migration_engine.extraction.engine

workbench:
	cd $(ROOT) && uv run streamlit run src/ehr_migration_engine/workbench/app.py
