from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .config import Settings
from .model_check import _directory_summary


MODEL_DOWNLOADS = {
    "3B": {
        "repo_id": "ByteDance-Seed/SeedVR2-3B",
        "description": "Official SeedVR2 3B checkpoint",
        "estimated_bytes": 14_600_000_000,
    },
    "7B": {
        "repo_id": "ByteDance-Seed/SeedVR2-7B",
        "description": "Official SeedVR2 7B checkpoint",
        "estimated_bytes": 66_900_000_000,
    },
}

ALLOW_PATTERNS = ["*.json", "*.safetensors", "*.pth", "*.bin", "*.py", "*.md", "*.txt"]
DownloadState = Literal["idle", "queued", "running", "complete", "failed"]


@dataclass
class DownloadJob:
    model: str
    status: DownloadState = "queued"
    repo_id: str = ""
    target_dir: str = ""
    message: str = "Waiting to start."
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    bytes_downloaded: int = 0
    estimated_bytes: int | None = None
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
        summary = _directory_summary(target_dir)
        job = active.get(model)
        if job:
            job["bytes_downloaded"] = summary["size_bytes"]
            statuses.append(job)
            continue
        statuses.append(
            {
                "model": model,
                "status": "complete" if summary["model_file_count"] > 0 else "idle",
                "repo_id": spec["repo_id"],
                "target_dir": str(target_dir),
                "message": "Model files are present." if summary["model_file_count"] > 0 else "Not downloaded.",
                "started_at": None,
                "finished_at": None,
                "error": None,
                "bytes_downloaded": summary["size_bytes"],
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
        if existing and existing.status in {"queued", "running"}:
            return _job_dict(existing)
        job = DownloadJob(
            model=model,
            repo_id=spec["repo_id"],
            target_dir=str(target_dir),
            estimated_bytes=spec["estimated_bytes"],
        )
        thread = threading.Thread(target=_download_worker, args=(settings, job), daemon=True)
        job.thread = thread
        _JOBS[model] = job
        thread.start()
        return _job_dict(job)


def _download_worker(settings: Settings, job: DownloadJob) -> None:
    _set_job(job, status="running", started_at=_now(), message="Downloading from Hugging Face.")
    target_dir = Path(job.target_dir)
    try:
        from huggingface_hub import snapshot_download

        cache_dir = settings.data_dir / "work" / "hf-cache" / job.model
        cache_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=job.repo_id,
            local_dir=str(target_dir),
            cache_dir=str(cache_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            allow_patterns=ALLOW_PATTERNS,
        )
        summary = _directory_summary(target_dir)
        _set_job(
            job,
            status="complete",
            finished_at=_now(),
            message="Download complete.",
            bytes_downloaded=int(summary["size_bytes"]),
        )
    except Exception as exc:
        summary = _directory_summary(target_dir)
        _set_job(
            job,
            status="failed",
            finished_at=_now(),
            message="Download failed.",
            error=str(exc),
            bytes_downloaded=int(summary["size_bytes"]),
        )


def _target_dir(settings: Settings, model: str) -> Path:
    return settings.seedvr2_model_dir / model


def _job_dict(job: DownloadJob) -> dict[str, Any]:
    return {
        "model": job.model,
        "status": job.status,
        "repo_id": job.repo_id,
        "target_dir": job.target_dir,
        "message": job.message,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error": job.error,
        "bytes_downloaded": job.bytes_downloaded,
        "estimated_bytes": job.estimated_bytes,
    }


def _set_job(job: DownloadJob, **updates: Any) -> None:
    with _LOCK:
        for key, value in updates.items():
            setattr(job, key, value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
