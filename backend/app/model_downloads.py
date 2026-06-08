from __future__ import annotations

import threading
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .config import Settings


MODEL_DOWNLOADS = {
    "3B": {
        "repo_id": "ByteDance-Seed/SeedVR2-3B",
        "description": "Official SeedVR2 3B checkpoint",
        "target_model": "3B",
        "estimated_bytes": 14_600_000_000,
        "files": ["ema_vae.pth", "pos_emb.pt", "neg_emb.pt", "seedvr2_ema_3b.pth"],
    },
    "7B": {
        "repo_id": "ByteDance-Seed/SeedVR2-7B",
        "description": "Official SeedVR2 7B checkpoint",
        "target_model": "7B",
        "estimated_bytes": 34_000_000_000,
        "files": ["ema_vae.pth", "seedvr2_ema_7b.pth"],
    },
    "7B-sharp": {
        "repo_id": "ByteDance-Seed/SeedVR2-7B",
        "description": "Official SeedVR2 7B sharp checkpoint",
        "target_model": "7B",
        "estimated_bytes": 34_000_000_000,
        "files": ["ema_vae.pth", "seedvr2_ema_7b_sharp.pth"],
    },
}

DownloadState = Literal["idle", "queued", "running", "canceling", "canceled", "complete", "failed"]


@dataclass
class DownloadJob:
    model: str
    status: DownloadState = "queued"
    repo_id: str = ""
    target_dir: str = ""
    files: list[str] = field(default_factory=list)
    message: str = "Waiting to start."
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    bytes_downloaded: int = 0
    estimated_bytes: int | None = None
    cache_dir: str | None = None
    cancel_requested: bool = False
    current_process: subprocess.Popen[Any] | None = field(default=None, repr=False)
    thread: threading.Thread | None = field(default=None, repr=False)


_LOCK = threading.Lock()
_JOBS: dict[str, DownloadJob] = {}


def model_download_options() -> list[dict[str, Any]]:
    return [{"model": model, **data} for model, data in MODEL_DOWNLOADS.items()]


def download_status(settings: Settings) -> list[dict[str, Any]]:
    with _LOCK:
        active = {model: _job_dict(job) for model, job in _JOBS.items()}
    statuses = []
    for model, spec in MODEL_DOWNLOADS.items():
        target_dir = _target_dir(settings, model)
        bytes_downloaded = _downloaded_bytes(target_dir, spec["files"])
        job = active.get(model)
        if job:
            job["bytes_downloaded"] = _active_downloaded_bytes(target_dir, spec["files"], job.get("cache_dir"), spec["estimated_bytes"])
            statuses.append(job)
            continue
        complete = _download_complete(target_dir, spec["files"])
        statuses.append(
            {
                "model": model,
                "status": "complete" if complete else "idle",
                "repo_id": spec["repo_id"],
                "target_dir": str(target_dir),
                "files": spec["files"],
                "message": "Selected files are present." if complete else "Not downloaded.",
                "started_at": None,
                "finished_at": None,
                "error": None,
                "bytes_downloaded": bytes_downloaded,
                "estimated_bytes": spec["estimated_bytes"],
            }
        )
    return statuses


def start_model_download(settings: Settings, model: str) -> dict[str, Any]:
    if model not in MODEL_DOWNLOADS:
        raise ValueError(f"Unknown downloadable model: {model}")
    spec = MODEL_DOWNLOADS[model]
    target_dir = _target_dir(settings, model)
    target_dir.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        existing = _JOBS.get(model)
        if existing and existing.status in {"queued", "running", "canceling"}:
            return _job_dict(existing)
        job = DownloadJob(
            model=model,
            repo_id=spec["repo_id"],
            target_dir=str(target_dir),
            files=list(spec["files"]),
            estimated_bytes=spec["estimated_bytes"],
        )
        thread = threading.Thread(target=_download_worker, args=(settings, job), daemon=True)
        job.thread = thread
        _JOBS[model] = job
        thread.start()
        return _job_dict(job)


def cancel_model_download(settings: Settings, model: str) -> dict[str, Any]:
    if model not in MODEL_DOWNLOADS:
        raise ValueError(f"Unknown downloadable model: {model}")
    with _LOCK:
        job = _JOBS.get(model)
        if not job or job.status not in {"queued", "running", "canceling"}:
            job = None
        else:
            job.cancel_requested = True
            job.status = "canceling"
            job.message = "Cancel requested. Stopping the active download."
            process = job.current_process
    if not job:
        status_by_model = {status["model"]: status for status in download_status(settings)}
        return status_by_model[model]
    if process and process.poll() is None:
        process.terminate()
    return _job_dict(job)


def _download_worker(settings: Settings, job: DownloadJob) -> None:
    _set_job(job, status="running", started_at=_now(), message="Downloading from Hugging Face.")
    target_dir = Path(job.target_dir)
    try:
        cache_dir = settings.data_dir / "work" / "hf-cache" / job.model
        cache_dir.mkdir(parents=True, exist_ok=True)
        _set_job(job, cache_dir=str(cache_dir))
        for filename in job.files:
            if _cancel_requested(job):
                _set_canceled(job, target_dir)
                return
            if (target_dir / filename).exists():
                _set_job(job, bytes_downloaded=_downloaded_bytes(target_dir, job.files))
                continue
            _download_file(job, target_dir, cache_dir, filename)
            if _cancel_requested(job):
                _set_canceled(job, target_dir)
                return
        _set_job(
            job,
            status="complete",
            finished_at=_now(),
            message="Download complete.",
            bytes_downloaded=_downloaded_bytes(target_dir, job.files),
        )
    except Exception as exc:
        if _cancel_requested(job):
            _set_canceled(job, target_dir)
            return
        _set_job(
            job,
            status="failed",
            finished_at=_now(),
            message="Download failed.",
            error=str(exc),
            bytes_downloaded=_downloaded_bytes(target_dir, job.files),
        )


def _target_dir(settings: Settings, model: str) -> Path:
    spec = MODEL_DOWNLOADS[model]
    return settings.seedvr2_model_dir / spec["target_model"]


def _download_file(job: DownloadJob, target_dir: Path, cache_dir: Path, filename: str) -> None:
    code = (
        "from huggingface_hub import hf_hub_download; "
        "import sys; "
        "hf_hub_download("
        "repo_id=sys.argv[1], filename=sys.argv[2], local_dir=sys.argv[3], "
        "cache_dir=sys.argv[4], local_dir_use_symlinks=False, resume_download=True"
        ")"
    )
    command = [sys.executable, "-c", code, job.repo_id, filename, str(target_dir), str(cache_dir)]
    process = subprocess.Popen(command)
    _set_job(
        job,
        current_process=process,
        message=f"Downloading {filename}.",
        bytes_downloaded=_active_downloaded_bytes(target_dir, job.files, str(cache_dir), job.estimated_bytes),
    )
    try:
        while process.poll() is None:
            if _cancel_requested(job):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                return
            _set_job(job, bytes_downloaded=_active_downloaded_bytes(target_dir, job.files, str(cache_dir), job.estimated_bytes))
            time.sleep(1)
        if process.returncode != 0:
            raise RuntimeError(f"Download failed for {filename} with exit code {process.returncode}")
    finally:
        _set_job(job, current_process=None, bytes_downloaded=_active_downloaded_bytes(target_dir, job.files, str(cache_dir), job.estimated_bytes))


def _download_complete(target_dir: Path, files: list[str]) -> bool:
    return bool(files) and all((target_dir / filename).exists() for filename in files)


def _downloaded_bytes(target_dir: Path, files: list[str]) -> int:
    total = 0
    for filename in files:
        path = target_dir / filename
        if path.exists():
            total += path.stat().st_size
    return total


def _active_downloaded_bytes(target_dir: Path, files: list[str], cache_dir: str | None, estimated_bytes: int | None) -> int:
    target_bytes = _downloaded_bytes(target_dir, files)
    cache_bytes = _directory_bytes(Path(cache_dir)) if cache_dir else 0
    total = max(target_bytes, cache_bytes)
    if estimated_bytes:
        return min(total, estimated_bytes)
    return total


def _directory_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _cancel_requested(job: DownloadJob) -> bool:
    with _LOCK:
        return job.cancel_requested


def _set_canceled(job: DownloadJob, target_dir: Path) -> None:
    _set_job(
        job,
        status="canceled",
        finished_at=_now(),
        message="Download canceled. Already completed files were kept for resume.",
        bytes_downloaded=_downloaded_bytes(target_dir, job.files),
        current_process=None,
    )


def _job_dict(job: DownloadJob) -> dict[str, Any]:
    return {
        "model": job.model,
        "status": job.status,
        "repo_id": job.repo_id,
        "target_dir": job.target_dir,
        "files": job.files,
        "message": job.message,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error": job.error,
        "bytes_downloaded": job.bytes_downloaded,
        "estimated_bytes": job.estimated_bytes,
        "cache_dir": job.cache_dir,
    }


def _set_job(job: DownloadJob, **updates: Any) -> None:
    with _LOCK:
        for key, value in updates.items():
            setattr(job, key, value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
