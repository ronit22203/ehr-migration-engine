#!/usr/bin/env bash
set -euo pipefail

# Always resolve paths from this file, so the export lands in the repo
# even when the script is started from another directory.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RAW_DIR="${ROOT}/data/01_raw/synthea"
JAR="${ROOT}/scripts/data_gen/synthea-with-dependencies.jar"

mkdir -p "$RAW_DIR"

echo "[*] Fetching Synthea engine..."
if [[ ! -f "$JAR" ]]; then
    curl -L -o "$JAR" \
        https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar
fi

echo "[*] Generating 10 synthetic patient histories into ${RAW_DIR}..."
# Run from the project root so any path Synthea still treats as relative
# stays inside the repo instead of the caller's working directory.
cd "$ROOT"
java -jar "$JAR" -p 10 -s 12345 \
    --exporter.baseDirectory="${RAW_DIR}/" \
    --exporter.fhir.export=true \
    --exporter.csv.export=true \
    --exporter.ccda.export=true

echo "[*] Synthea generation complete. Data staged in ${RAW_DIR}"
