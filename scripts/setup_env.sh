#!/usr/bin/env bash
# Idempotent bootstrap for a Runpod GPU pod (or any Ubuntu 22.04+ host).
#
# Runpod pods cannot nest Docker or Docker Compose — the platform already runs
# your workload as a container. This script installs Neo4j and Ollama natively
# instead of using docker compose. Local laptops still use docker-compose.yml.
#
# Usage (from anywhere on the pod):
#   export EHR_MIGRATION_ROOT=/workspace/ehr-migration-engine   # optional
#   bash /workspace/ehr-migration-engine/scripts/setup_env.sh
#
# Optional env flags:
#   SKIP_OLLAMA_PULL=1   skip `ollama pull medgemma:4b`
#   SKIP_NEO4J=1         skip Neo4j install/start
#   SKIP_UI_BUILD=1      skip workbench npm install + build
#   NEO4J_PASSWORD=...   default: password (matches local docker-compose)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${EHR_MIGRATION_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
NEO4J_VERSION_MAJOR="5"
export DEBIAN_FRONTEND=noninteractive

log() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# Runpod pods (and most containers) are already root and often lack sudo.
# Strip sudo-only flags (e.g. -E from `sudo -E bash -`) before exec.
sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    local -a args=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        -E|-H|-n|-s|-i|-K|-k|-l|-v|-V|-h)
          shift
          ;;
        -u|-g|-C|-p|-D|-T|-R|-U)
          shift 2
          ;;
        --)
          shift
          args+=("$@")
          break
          ;;
        *)
          args+=("$@")
          break
          ;;
      esac
    done
    "${args[@]}"
  elif need_cmd sudo; then
    command sudo "$@"
  else
    die "need root or sudo to install packages (EUID=$(id -u))"
  fi
}

ensure_path() {
  # uv and npm often land outside the non-login PATH.
  export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"
  if [[ -d /usr/lib/jvm ]]; then
    # Neo4j needs a Java on PATH for cypher-shell in some installs.
    :
  fi
}

install_system_packages() {
  log "Installing system packages"
  if need_cmd apt-get; then
    sudo apt-get update -y
    sudo apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      gnupg \
      wget \
      build-essential \
      openjdk-17-jre-headless \
      libgl1 \
      libglib2.0-0 \
      lsb-release \
      apt-transport-https \
      zstd
  else
    die "apt-get not found; this script targets Ubuntu/Debian Runpod images"
  fi
}

install_uv() {
  ensure_path
  if need_cmd uv; then
    log "uv already installed: $(uv --version)"
    return
  fi
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ensure_path
  need_cmd uv || die "uv install failed"
}

install_node() {
  ensure_path
  if need_cmd node && need_cmd npm; then
    local major
    major="$(node -v | sed -E 's/^v([0-9]+).*/\1/')"
    if [[ "${major}" -ge 20 ]]; then
      log "Node already installed: $(node -v)"
      return
    fi
    warn "Node $(node -v) is older than 20; upgrading via NodeSource"
  fi

  log "Installing Node.js 22 (NodeSource)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y --no-install-recommends nodejs
  need_cmd node || die "Node install failed"
  log "Node $(node -v), npm $(npm -v)"
}

install_python_deps() {
  ensure_path
  [[ -f "${ROOT}/pyproject.toml" ]] || die "pyproject.toml not found under ${ROOT}"
  log "Syncing Python deps with uv (root=${ROOT})"
  (cd "${ROOT}" && uv sync)
}

install_ollama() {
  ensure_path
  if ! need_cmd ollama; then
    log "Installing Ollama"
    curl -fsSL https://ollama.com/install.sh | sh
    need_cmd ollama || die "Ollama install failed"
  else
    log "Ollama already installed: $(ollama --version 2>/dev/null || echo ok)"
  fi

  if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    log "Starting ollama serve in background"
    # Prefer systemd when available; otherwise nohup (typical in containers).
    if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files ollama.service >/dev/null 2>&1; then
      sudo systemctl enable --now ollama || true
    fi
    if ! curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      nohup ollama serve >/tmp/ollama.log 2>&1 &
      sleep 2
    fi
  else
    log "Ollama API already responding on :11434"
  fi

  if [[ "${SKIP_OLLAMA_PULL:-0}" == "1" ]]; then
    log "SKIP_OLLAMA_PULL=1 — not pulling medgemma:4b"
  else
    log "Pulling Ollama model medgemma:4b (used by extraction/engine.py)"
    ollama pull medgemma:4b
  fi
}

install_neo4j() {
  if [[ "${SKIP_NEO4J:-0}" == "1" ]]; then
    log "SKIP_NEO4J=1 — skipping Neo4j"
    return
  fi

  ensure_path

  if ! need_cmd neo4j && ! [[ -x /usr/bin/neo4j ]]; then
    log "Installing Neo4j ${NEO4J_VERSION_MAJOR} from official apt repo"
    # https://neo4j.com/docs/operations-manual/current/installation/linux/debian/
    wget -qO - https://debian.neo4j.com/neotechnology.gpg.key \
      | sudo gpg --dearmor -o /usr/share/keyrings/neotechnology.gpg
    echo "deb [signed-by=/usr/share/keyrings/neotechnology.gpg] https://debian.neo4j.com stable ${NEO4J_VERSION_MAJOR}" \
      | sudo tee /etc/apt/sources.list.d/neo4j.list >/dev/null
    sudo apt-get update -y
    # Pin to community 5.x line available from the stable-5 suite.
    sudo apt-get install -y --no-install-recommends neo4j
  else
    log "Neo4j already installed"
  fi

  local conf="/etc/neo4j/neo4j.conf"
  if [[ -f "${conf}" ]]; then
    log "Configuring Neo4j listen addresses and heap"
    sudo sed -i 's/^#\?server.default_listen_address=.*/server.default_listen_address=0.0.0.0/' "${conf}" || true
    if ! grep -q '^server.memory.heap.initial_size=' "${conf}"; then
      echo 'server.memory.heap.initial_size=2g' | sudo tee -a "${conf}" >/dev/null
    else
      sudo sed -i 's/^server.memory.heap.initial_size=.*/server.memory.heap.initial_size=2g/' "${conf}"
    fi
    if ! grep -q '^server.memory.heap.max_size=' "${conf}"; then
      echo 'server.memory.heap.max_size=2g' | sudo tee -a "${conf}" >/dev/null
    else
      sudo sed -i 's/^server.memory.heap.max_size=.*/server.memory.heap.max_size=2g/' "${conf}"
    fi
  fi

  log "Setting Neo4j auth (neo4j / \${NEO4J_PASSWORD})"
  # neo4j-admin set-initial-password is a no-op once the DB has been started.
  if sudo neo4j-admin dbms set-initial-password "${NEO4J_PASSWORD}" 2>/dev/null \
    || sudo neo4j-admin set-initial-password "${NEO4J_PASSWORD}" 2>/dev/null; then
    :
  else
    warn "Could not set initial Neo4j password (DB may already be initialized)"
  fi

  log "Starting Neo4j"
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl enable neo4j || true
    sudo systemctl restart neo4j || sudo neo4j start || true
  else
    sudo neo4j restart 2>/dev/null || sudo neo4j start || true
  fi

  # Wait briefly for Bolt.
  local i
  for i in $(seq 1 30); do
    if curl -fsS --max-time 2 http://127.0.0.1:7474 >/dev/null 2>&1; then
      log "Neo4j HTTP responding on :7474"
      break
    fi
    sleep 2
  done
}

build_workbench_ui() {
  if [[ "${SKIP_UI_BUILD:-0}" == "1" ]]; then
    log "SKIP_UI_BUILD=1 — skipping workbench UI build"
    return
  fi
  ensure_path
  local ui="${ROOT}/workbench-ui"
  [[ -d "${ui}" ]] || die "workbench-ui missing at ${ui}"
  log "Installing workbench-ui npm deps and building"
  if [[ -f "${ui}/package-lock.json" ]]; then
    (cd "${ui}" && npm ci)
  else
    (cd "${ui}" && npm install)
  fi
  (cd "${ROOT}" && make workbench-ui)
}

health_checks() {
  ensure_path
  log "Running health checks"
  local failed=0

  if need_cmd nvidia-smi; then
    nvidia-smi || { warn "nvidia-smi failed"; failed=1; }
  else
    warn "nvidia-smi not found (CPU-only host?)"
  fi

  if (cd "${ROOT}" && uv run python -c 'import torch; print("cuda:", torch.cuda.is_available())'); then
    :
  else
    warn "torch CUDA probe failed"
    failed=1
  fi

  if curl -fsS --max-time 5 http://127.0.0.1:11434/api/tags >/dev/null; then
    log "Ollama OK"
  else
    warn "Ollama not responding on :11434"
    failed=1
  fi

  if [[ "${SKIP_NEO4J:-0}" != "1" ]]; then
    if need_cmd cypher-shell; then
      if cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" 'RETURN 1 AS ok' >/dev/null 2>&1; then
        log "Neo4j Bolt OK"
      else
        warn "cypher-shell ping failed (Neo4j may still be starting; re-run later)"
        failed=1
      fi
    else
      warn "cypher-shell not on PATH"
      failed=1
    fi
  fi

  if [[ "${failed}" -ne 0 ]]; then
    warn "Some health checks failed — see messages above"
    return 1
  fi
  log "All health checks passed"
}

main() {
  log "EHR Migration Engine bootstrap"
  log "ROOT=${ROOT}"
  log "Skipping Docker/Compose (unsupported inside Runpod pods)"

  [[ -d "${ROOT}" ]] || die "Repo root not found: ${ROOT}"

  install_system_packages
  install_uv
  install_node
  install_python_deps
  install_ollama
  install_neo4j
  build_workbench_ui
  health_checks || true

  cat <<EOF

Bootstrap complete.

Next (on the pod):
  cd ${ROOT}
  # Serve workbench on all interfaces so Runpod HTTP proxy can reach it:
  uv run uvicorn ehr_migration_engine.workbench.api:app --host 0.0.0.0 --port 8501
  # Pipeline stages: make ocr / extract / normalize / graph / fhir

EOF
}

main "$@"
