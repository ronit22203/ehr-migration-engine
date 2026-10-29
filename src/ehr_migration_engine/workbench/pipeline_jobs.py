"""Run allowlisted Makefile targets from the workbench UI."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ehr_migration_engine.workbench.paths import PROJECT_ROOT

PIPELINE_ACTIONS: dict[str, dict[str, str]] = {
    "data-run-raw": {
        "label": "Split drop (data-run-raw)",
        "description": "Copy data/01_raw/faxes into triage and split each PDF into pages.",
        "make": "data-run-raw",
    },
    "triage-pdfs": {
        "label": "Resplit pages",
        "description": "Split PDFs already in data/02_triage/unstructured.",
        "make": "triage-pdfs",
    },
    "ocr": {
        "label": "OCR",
        "description": "Run Surya OCR on atomic pages.",
        "make": "ocr",
    },
    "parse": {
        "label": "Parse OCR text",
        "description": "Rebuild OCR JSON into reading-order plain text.",
        "make": "parse",
    },
    "extract": {
        "label": "Extract",
        "description": "Parse OCR text, then extract clinical JSON via Ollama.",
        "make": "extract",
    },
    "normalize": {
        "label": "Normalize",
        "description": "Code conditions, medications, and labs into data/04_normalized.",
        "make": "normalize",
    },
    "graph": {
        "label": "Build graph",
        "description": "Load normalized pages into local Neo4j.",
        "make": "graph",
    },
    "fhir": {
        "label": "Serialize FHIR",
        "description": "Write FHIR R4 transaction bundles to data/05_fhir.",
        "make": "fhir",
    },
    "clean-ocr": {
        "label": "Clean OCR",
        "description": "Delete data/03_ocr.",
        "make": "clean-ocr",
    },
    "clean-extract": {
        "label": "Clean extract",
        "description": "Delete data/04_structured.",
        "make": "clean-extract",
    },
    "clean-normalize": {
        "label": "Clean normalize",
        "description": "Delete data/04_normalized.",
        "make": "clean-normalize",
    },
    "clean": {
        "label": "Clean all stages",
        "description": "Delete OCR, extraction, and normalization output.",
        "make": "clean",
    },
}


@dataclass
class PipelineJob:
    action: str
    label: str
    status: str = "idle"
    started_at: float | None = None
    finished_at: float | None = None
    returncode: int | None = None
    log: str = ""
    error: str | None = None


@dataclass
class _JobState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    job: PipelineJob = field(default_factory=lambda: PipelineJob(action="", label="Idle", status="idle"))
    process: subprocess.Popen[str] | None = None
    cancel_requested: bool = False


_STATE = _JobState()


def list_actions() -> list[dict[str, str]]:
    return [
        {"id": action_id, "label": meta["label"], "description": meta["description"], "make": meta["make"]}
        for action_id, meta in PIPELINE_ACTIONS.items()
    ]


def job_status() -> dict:
    with _STATE.lock:
        payload = asdict(_STATE.job)
    return payload


def start_job(action_id: str, *, root: Path | None = None) -> dict:
    if action_id not in PIPELINE_ACTIONS:
        raise ValueError(f"Unknown pipeline action: {action_id}")
    meta = PIPELINE_ACTIONS[action_id]
    project = (root or PROJECT_ROOT).resolve()
    makefile = project / "Makefile"
    if not makefile.is_file():
        raise FileNotFoundError(f"Makefile not found at {makefile}")

    with _STATE.lock:
        if _STATE.job.status == "running":
            raise RuntimeError(f"Pipeline already running: {_STATE.job.action}")
        _STATE.cancel_requested = False
        _STATE.job = PipelineJob(
            action=action_id,
            label=meta["label"],
            status="running",
            started_at=time.time(),
            log=f"$ make {meta['make']}\n",
        )

    thread = threading.Thread(
        target=_run_make,
        args=(meta["make"], project),
        daemon=True,
        name=f"pipeline-{action_id}",
    )
    thread.start()
    return job_status()


def kill_job(*, root: Path | None = None) -> dict:
    """Stop the in-flight make job (process group) and any stray pipeline workers."""
    project = (root or PROJECT_ROOT).resolve()
    with _STATE.lock:
        if _STATE.job.status != "running":
            raise RuntimeError("No pipeline job is running.")
        _STATE.cancel_requested = True
        process = _STATE.process
        action = _STATE.job.action or "pipeline"
        _STATE.job.log += "\n[kill requested]\n"

    if process is not None and process.poll() is None:
        _terminate_process_tree(process)

    # Also clear any orphaned CLI workers that outlived `make`.
    _run_make_kill_pipeline(project)

    with _STATE.lock:
        if _STATE.job.status == "running":
            _STATE.job.status = "cancelled"
            _STATE.job.finished_at = time.time()
            _STATE.job.error = f"Pipeline cancelled: {action}"
            _STATE.job.log += "[cancelled]\n"
            _STATE.process = None
        return asdict(_STATE.job)


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.terminate()
        except ProcessLookupError:
            return

    try:
        process.wait(timeout=3)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass


def _run_make_kill_pipeline(project: Path) -> None:
    makefile = project / "Makefile"
    if not makefile.is_file():
        return
    try:
        subprocess.run(
            ["make", "kill-pipeline"],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def _run_make(target: str, project: Path) -> None:
    try:
        process = subprocess.Popen(
            ["make", target],
            cwd=str(project),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
    except Exception as exc:
        with _STATE.lock:
            _STATE.job.status = "failed"
            _STATE.job.finished_at = time.time()
            _STATE.job.error = str(exc)
            _STATE.job.log += f"\n[failed to start] {exc}\n"
        return

    with _STATE.lock:
        _STATE.process = process
        cancel_requested = _STATE.cancel_requested

    if cancel_requested:
        _terminate_process_tree(process)

    assert process.stdout is not None
    for line in process.stdout:
        with _STATE.lock:
            _STATE.job.log += line
            if len(_STATE.job.log) > 200_000:
                _STATE.job.log = _STATE.job.log[-160_000:]

    code = process.wait()
    with _STATE.lock:
        cancelled = _STATE.cancel_requested
        _STATE.process = None
        _STATE.job.returncode = code
        _STATE.job.finished_at = time.time()
        if cancelled or _STATE.job.status == "cancelled":
            _STATE.job.status = "cancelled"
            _STATE.job.error = _STATE.job.error or f"Pipeline cancelled: {target}"
            if "[cancelled]" not in _STATE.job.log:
                _STATE.job.log += "\n[cancelled]\n"
        elif code == 0:
            _STATE.job.status = "succeeded"
        else:
            _STATE.job.status = "failed"
            _STATE.job.error = f"make {target} exited with code {code}"
            _STATE.job.log += f"\n[exit {code}]\n"
