.DEFAULT_GOAL := help

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
UV   := uv run --project $(ROOT) python

.PHONY: help data-synthea data-mtsamples data-faxes data-notes data-raw triage-pdfs

help:
	@printf '%s\n' \
		'Populate data/01_raw/ with synthetic clinical records.' \
		'' \
		'  make data-synthea     10 Synthea patients (FHIR, CSV, CCDA)' \
		'  make data-mtsamples   MTSamples notes (full CSV and 24 long text files)' \
		'  make data-faxes       8 multi-page fax packets from those notes' \
		'  make data-notes       notes, then faxes' \
		'  make data-raw         all three generators, in order' \
		'' \
		'  make triage-pdfs      split data/02_triage/unstructured into single pages'

data-synthea:
	$(ROOT)/scripts/data_gen/run_synthea.sh

data-mtsamples:
	$(UV) $(ROOT)/scripts/data_gen/fetch_mtsamples.py

data-faxes:
	$(UV) $(ROOT)/scripts/data_gen/dirty_fax_gen.py

data-notes: data-mtsamples data-faxes

data-raw: data-synthea data-notes

triage-pdfs:
	$(UV) -m ehr_migration_engine.ingestion.pdf_handler
