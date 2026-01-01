"""Background worker that runs analysis jobs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import threading
from pathlib import Path

from api.db import claim_next_job, delete_job, init_db, set_job_progress, set_job_status

APP_ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = (APP_ROOT / "storage").resolve()
DB_PATH = STORAGE_ROOT / "jobs.db"

GENERATOR_REPO = Path(os.environ.get("GENERATOR_REPO", ""))
GENERATOR_CONFIG = Path(os.environ.get("GENERATOR_CONFIG", ""))

POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "1.0"))


class JobFailure(Exception):
    def __init__(self, message: str, output_lines: list[str] | None = None) -> None:
        super().__init__(message)
        self.output_lines = output_lines or []


def _abs_storage_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        if path.exists():
            return path
        audio_candidate = STORAGE_ROOT / "audio" / path.name
        if audio_candidate.exists():
            return audio_candidate
        analysis_candidate = STORAGE_ROOT / "analysis" / path.name
        if analysis_candidate.exists():
            return analysis_candidate
        return path
    return (STORAGE_ROOT / path).resolve()


def run_job(job_id: str, input_path: str, output_path: str) -> None:
    if not GENERATOR_REPO.exists() or not GENERATOR_CONFIG.exists():
        raise RuntimeError("GENERATOR_REPO or GENERATOR_CONFIG is not set or missing")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(GENERATOR_REPO)
    env["FJ_PROGRESS"] = "1"

    input_abs = _abs_storage_path(input_path)
    if not input_abs.exists():
        candidates = sorted((STORAGE_ROOT / "audio").glob(f"{job_id}.*"))
        if candidates:
            input_abs = candidates[0]
    output_abs = _abs_storage_path(output_path)
    output_abs.parent.mkdir(parents=True, exist_ok=True)

    progress_lock = threading.Lock()
    progress_state = {"value": 0, "last_update": time.time()}
    stop_event = threading.Event()

    def bump_progress() -> None:
        while not stop_event.is_set():
            with progress_lock:
                current = progress_state["value"]
                last_update = progress_state["last_update"]
            if current >= 75:
                break
            if current >= 50 and time.time() - last_update > 1.0:
                next_value = min(75, current + 1)
                set_job_progress(DB_PATH, job_id, next_value)
                with progress_lock:
                    progress_state["value"] = next_value
                    progress_state["last_update"] = time.time()
            stop_event.wait(0.5)

    progress_thread = threading.Thread(target=bump_progress, daemon=True)
    progress_thread.start()

    cmd = [
        sys.executable,
        "-m",
        "app.main",
        str(input_abs),
        "-o",
        str(output_abs),
        "--config",
        str(GENERATOR_CONFIG),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        cwd=str(GENERATOR_REPO),
        bufsize=1,
    )
    assert proc.stdout is not None
    output_lines: list[str] = []
    for line in proc.stdout:
        if line.startswith("PROGRESS:"):
            parts = line.strip().split(":", 2)
            if len(parts) >= 2:
                try:
                    progress = int(parts[1])
                    set_job_progress(DB_PATH, job_id, progress)
                    with progress_lock:
                        progress_state["value"] = progress
                        progress_state["last_update"] = time.time()
                except ValueError:
                    pass
            continue
        output_lines.append(line)
        print(line, end="")
    returncode = proc.wait()
    stop_event.set()
    progress_thread.join(0.5)
    if returncode != 0:
        raise JobFailure(f"Engine exited with status {returncode}", output_lines)


def apply_track_metadata(output_path: str, title: str | None, artist: str | None) -> None:
    if not title and not artist:
        return
    result_path = _abs_storage_path(output_path)
    if not result_path.exists():
        return
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return
    track = data.get("track") if isinstance(data, dict) else None
    if not isinstance(track, dict):
        track = {}
        data["track"] = track
    if title:
        track["title"] = title
    if artist:
        track["artist"] = artist
    result_path.write_text(json.dumps(data), encoding="utf-8")


def cleanup_failed_job(job, error: Exception) -> None:
    log_dir = STORAGE_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job.id}.log"
    output_lines: list[str] = []
    if isinstance(error, JobFailure):
        output_lines = error.output_lines
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Job failed: {error}\n")
        if output_lines:
            log_file.write("\n--- Engine output ---\n")
            for line in output_lines:
                log_file.write(line)
    if job.input_path:
        input_path = _abs_storage_path(job.input_path)
        if input_path.is_file():
            input_path.unlink()
    if job.output_path:
        output_path = _abs_storage_path(job.output_path)
        if output_path.is_file():
            output_path.unlink()
    delete_job(DB_PATH, job.id)
    print(f"Job {job.id} failed: {error} (log: {log_path})")


def main() -> None:
    init_db(DB_PATH)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "audio").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "analysis").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "logs").mkdir(parents=True, exist_ok=True)

    while True:
        job = claim_next_job(DB_PATH)
        if not job:
            time.sleep(POLL_INTERVAL_S)
            continue
        try:
            run_job(job.id, job.input_path, job.output_path)
            apply_track_metadata(job.output_path, job.track_title, job.track_artist)
            set_job_progress(DB_PATH, job.id, 100)
        except Exception as exc:
            cleanup_failed_job(job, exc)
            continue
        set_job_status(DB_PATH, job.id, "complete", None)


if __name__ == "__main__":
    main()
