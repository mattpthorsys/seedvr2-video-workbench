from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping

from .config import Settings
from .db import row_to_dict, utc_now
from .eta import estimate_job, smooth_eta
from .file_browser import resolve_managed_path
from .gpu import read_gpu_snapshot
from .models import PIPELINE_STAGES, TERMINAL_JOB_STATUSES
from .pipeline.encode import build_encode_command
from .pipeline.ffmpeg import build_lossless_intermediate_command, run_command
from .pipeline.seedvr2 import SeedVR2Adapter
from .pipeline.stats import update_performance_profiles
from .schemas import EncodeOptions, JobCreate, PreprocessOptions, SeedVR2Options
from .video_probe import run_ffprobe


TARGET_HEIGHTS = {"720p": 720, "1080p": 1080, "1440p": 1440, "4k": 2160}


def _model_dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _target_size(request: Mapping[str, Any], source_width: int | None, source_height: int | None) -> tuple[int | None, int | None]:
    target = request.get("target") or {}
    mode = target.get("mode", "1080p")
    if mode == "keep":
        return source_width, source_height
    if mode == "custom":
        return target.get("width"), target.get("height")
    target_height = TARGET_HEIGHTS.get(mode)
    if not target_height:
        return None, None
    aspect = (source_width / source_height) if source_width and source_height else (16 / 9)
    return int(round(target_height * aspect / 2) * 2), target_height


OUTPUT_CONTAINERS = {"mkv", "mp4", "mov", "webm"}


def _output_path(settings: Settings, input_path: str, container: str | None = None) -> str:
    stem = Path(input_path).stem or "video"
    suffix = container if container in OUTPUT_CONTAINERS else "mkv"
    return str(settings.data_dir / "output" / f"{stem}_restored.{suffix}")


def _metadata_values(request: Mapping[str, Any]) -> dict[str, Any]:
    metadata = request.get("source_metadata") or {}
    return {
        "source_width": metadata.get("width"),
        "source_height": metadata.get("height"),
        "source_fps": metadata.get("frame_rate"),
        "source_frame_count": metadata.get("frame_count_estimate"),
        "source_duration_seconds": metadata.get("duration_seconds"),
    }


def _ensure_metadata(settings: Settings, data: dict[str, Any]) -> None:
    if data.get("source_metadata"):
        return
    path = resolve_managed_path(settings, data["input_path"], "input", must_exist=True)
    metadata = run_ffprobe(path, settings.ffprobe_path)
    data["source_metadata"] = metadata.model_dump() if hasattr(metadata, "model_dump") else metadata.dict()


def _resolve_encode_options(settings: Settings, encode: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(encode)
    hardware = resolved.get("hardware") or "auto"
    if hardware == "auto":
        gpu = read_gpu_snapshot().as_dict()
        resolved["hardware"] = "nvenc" if settings.prefer_gpu and gpu.get("available") else "cpu"
    if resolved.get("container") not in OUTPUT_CONTAINERS:
        resolved["container"] = "mkv"
    if not resolved.get("audio_mode"):
        resolved["audio_mode"] = "copy" if resolved.get("copy_audio", True) else "none"
    if resolved["container"] == "webm":
        resolved["codec"] = "av1"
        if resolved.get("audio_mode") == "copy":
            resolved["audio_mode"] = "opus"
    if resolved["container"] in {"mp4", "mov"} and resolved.get("audio_mode") == "opus":
        resolved["audio_mode"] = "aac"
    return resolved


def create_job(conn: sqlite3.Connection, settings: Settings, request: JobCreate | Mapping[str, Any]) -> dict[str, Any]:
    data = _model_dump(request)
    _ensure_metadata(settings, data)
    metadata = _metadata_values(data)
    target_width, target_height = _target_size(data, metadata["source_width"], metadata["source_height"])
    seedvr2 = data.get("seedvr2") or {}
    encode = _resolve_encode_options(settings, data.get("encode") or {})
    data["encode"] = encode
    now = utc_now()
    options_json = json.dumps(data, sort_keys=True)

    estimate_context = {
        **metadata,
        "target_width": target_width,
        "target_height": target_height,
        "preset": data.get("preset"),
        "seedvr2_model": seedvr2.get("model"),
        "seedvr2_precision": seedvr2.get("precision"),
        "batch_size": seedvr2.get("batch_size"),
        "temporal_overlap": seedvr2.get("temporal_overlap"),
        "encoder": f"{encode.get('codec')}-{encode.get('hardware')}",
        "frames_total": metadata.get("source_frame_count") or 300,
    }
    estimate = estimate_job(conn, estimate_context)

    req_output_path = data.get("output_path")
    if req_output_path:
        out_path_path = resolve_managed_path(settings, req_output_path, "output", must_exist=False)
        out_path_path.parent.mkdir(parents=True, exist_ok=True)
        out_path = str(out_path_path)
    else:
        out_path = _output_path(settings, data["input_path"], encode.get("container"))

    cursor = conn.execute(
        """
        INSERT INTO jobs (
          input_path, output_path, status, created_at, updated_at,
          source_width, source_height, source_fps, source_frame_count, source_duration_seconds,
          target_width, target_height, preset, seedvr2_model, seedvr2_precision, batch_size,
          temporal_overlap, encoder, crf, estimated_total_seconds_initial,
          eta_confidence_initial, frames_total, options_json
        ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["input_path"],
            out_path,
            now,
            now,
            metadata["source_width"],
            metadata["source_height"],
            metadata["source_fps"],
            metadata["source_frame_count"],
            metadata["source_duration_seconds"],
            target_width,
            target_height,
            data.get("preset"),
            seedvr2.get("model"),
            seedvr2.get("precision"),
            seedvr2.get("batch_size"),
            seedvr2.get("temporal_overlap"),
            f"{encode.get('codec')}-{encode.get('hardware')}",
            encode.get("quality"),
            estimate["estimated_total_seconds"],
            estimate["confidence"],
            metadata["source_frame_count"] or 300,
            options_json,
        ),
    )
    job_id = int(cursor.lastrowid)
    log_path = settings.data_dir / "logs" / f"job-{job_id}.log"
    conn.execute("UPDATE jobs SET log_path = ? WHERE id = ?", (str(log_path), job_id))
    conn.commit()
    append_log(conn, job_id, "Job queued.")
    return get_job(conn, job_id) or {}


def list_jobs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC, id DESC").fetchall()
    return [row_to_dict(row) or {} for row in rows]


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def get_stage_stats(conn: sqlite3.Connection, job_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM job_stage_stats WHERE job_id = ? ORDER BY id",
        (job_id,),
    ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def cancel_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    job = get_job(conn, job_id)
    if not job:
        return None
    if job["status"] in TERMINAL_JOB_STATUSES:
        return job
    conn.execute(
        "UPDATE jobs SET cancel_requested = 1, updated_at = ? WHERE id = ?",
        (utc_now(), job_id),
    )
    conn.commit()
    append_log(conn, job_id, "Cancellation requested.")
    return get_job(conn, job_id)


def append_log(conn: sqlite3.Connection, job_id: int, message: str) -> None:
    job = get_job(conn, job_id)
    if not job:
        return
    log_path = Path(job["log_path"] or f"job-{job_id}.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] {message}\n")


def read_logs(conn: sqlite3.Connection, job_id: int, limit_bytes: int = 200_000) -> str:
    job = get_job(conn, job_id)
    if not job or not job.get("log_path"):
        return ""
    path = Path(job["log_path"])
    if not path.exists():
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > limit_bytes:
            handle.seek(size - limit_bytes)
        return handle.read().decode("utf-8", errors="replace")


def acquire_next_job(conn: sqlite3.Connection) -> int | None:
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute("SELECT id FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1").fetchone()
    if not row:
        conn.commit()
        return None
    now = utc_now()
    conn.execute(
        "UPDATE jobs SET status = 'running', started_at = ?, updated_at = ? WHERE id = ?",
        (now, now, row["id"]),
    )
    conn.commit()
    return int(row["id"])


def _start_stage(conn: sqlite3.Connection, job: Mapping[str, Any], stage_name: str, frames_total: int) -> int:
    now = utc_now()
    cursor = conn.execute(
        """
        INSERT INTO job_stage_stats (
          job_id, stage_name, status, started_at, frames_total, frames_processed,
          input_width, input_height, output_width, output_height, options_json
        ) VALUES (?, ?, 'running', ?, ?, 0, ?, ?, ?, ?, ?)
        """,
        (
            job["id"],
            stage_name,
            now,
            frames_total,
            job.get("source_width"),
            job.get("source_height"),
            job.get("target_width"),
            job.get("target_height"),
            job.get("options_json") or "{}",
        ),
    )
    conn.execute(
        "UPDATE jobs SET current_stage = ?, updated_at = ? WHERE id = ?",
        (stage_name, now, job["id"]),
    )
    conn.commit()
    append_log(conn, int(job["id"]), f"Stage started: {stage_name}.")
    return int(cursor.lastrowid)


def _update_progress(
    conn: sqlite3.Connection,
    job_id: int,
    stage_id: int,
    stage_name: str,
    stage_index: int,
    frames_processed: int,
    frames_total: int,
) -> None:
    progress = min(1.0, max(0.0, (stage_index + (frames_processed / max(frames_total, 1))) / len(PIPELINE_STAGES)))
    now = utc_now()
    conn.execute(
        """
        UPDATE job_stage_stats
        SET frames_processed = ?
        WHERE id = ?
        """,
        (frames_processed, stage_id),
    )
    conn.execute(
        """
        UPDATE jobs
        SET current_stage = ?, frames_processed = ?, progress = ?, updated_at = ?
        WHERE id = ?
        """,
        (stage_name, frames_processed, progress, now, job_id),
    )
    conn.commit()


def _finish_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    status: str,
    frames_processed: int,
    frames_total: int,
    started_monotonic: float,
    gpu_samples: list[dict[str, Any]],
) -> None:
    elapsed = max(time.monotonic() - started_monotonic, 0.001)
    gpu_available = [sample for sample in gpu_samples if sample.get("available")]
    peak_vram = max((float(sample.get("memory_used_mb") or 0) for sample in gpu_available), default=None)
    avg_util = (
        sum(float(sample.get("utilisation_percent") or 0) for sample in gpu_available) / len(gpu_available)
        if gpu_available
        else None
    )
    avg_vram = (
        sum(float(sample.get("memory_used_mb") or 0) for sample in gpu_available) / len(gpu_available)
        if gpu_available
        else None
    )
    conn.execute(
        """
        UPDATE job_stage_stats
        SET status = ?, finished_at = ?, elapsed_seconds = ?, frames_total = ?, frames_processed = ?,
            effective_fps = ?, peak_vram_mb = ?, average_gpu_utilisation = ?, average_vram_mb = ?,
            completed_sample = ?
        WHERE id = ?
        """,
        (
            status,
            utc_now(),
            elapsed,
            frames_total,
            frames_processed,
            frames_processed / elapsed if elapsed > 0 else None,
            peak_vram,
            avg_util,
            avg_vram,
            1 if status == "complete" and frames_processed >= frames_total else 0,
            stage_id,
        ),
    )
    conn.commit()


def _mark_complete(conn: sqlite3.Connection, job_id: int, status: str, started_monotonic: float, error: str | None = None) -> None:
    now = utc_now()
    elapsed = max(time.monotonic() - started_monotonic, 0.001)
    conn.execute(
        """
        UPDATE jobs
        SET status = ?, finished_at = ?, updated_at = ?, total_elapsed_seconds = ?,
            progress = CASE WHEN ? = 'complete' THEN 1 ELSE progress END,
            error_message = COALESCE(?, error_message)
        WHERE id = ?
        """,
        (status, now, now, elapsed, status, error, job_id),
    )
    conn.commit()
    append_log(conn, job_id, f"Job {status}.")


def run_job(conn: sqlite3.Connection, job_id: int, settings: Settings, sleep_seconds: float = 0.2) -> dict[str, Any]:
    job_started = time.monotonic()
    job = get_job(conn, job_id)
    if not job:
        raise ValueError(f"Job {job_id} does not exist")
    if job["status"] == "queued":
        now = utc_now()
        conn.execute("UPDATE jobs SET status = 'running', started_at = ?, updated_at = ? WHERE id = ?", (now, now, job_id))
        conn.commit()
        job = get_job(conn, job_id) or job

    gpu = read_gpu_snapshot().as_dict()
    conn.execute(
        "UPDATE jobs SET gpu_name = ?, driver_version = ?, cuda_version = ? WHERE id = ?",
        (gpu.get("name"), gpu.get("driver_version"), gpu.get("cuda_version"), job_id),
    )
    conn.commit()
    if settings.require_gpu_for_real_pipeline and not settings.mock_pipeline and not gpu.get("available"):
        message = "GPU is required for the real SeedVR2 pipeline, but nvidia-smi is not visible."
        _mark_complete(conn, job_id, "failed", job_started, message)
        return get_job(conn, job_id) or {}
    append_log(conn, job_id, "Pipeline runner is using the mock stage executor." if settings.mock_pipeline else "Pipeline runner started.")

    if not settings.mock_pipeline:
        return _run_real_job(conn, job, settings, job_started)

    try:
        frames_total = max(int(job.get("frames_total") or job.get("source_frame_count") or 300), 1)
        live_eta: float | None = job.get("estimated_total_seconds_initial")
        for stage_index, stage_name in enumerate(PIPELINE_STAGES):
            job = get_job(conn, job_id) or job
            if int(job.get("cancel_requested") or 0):
                _mark_complete(conn, job_id, "cancelled", job_started)
                return get_job(conn, job_id) or {}

            stage_frames = 1 if stage_name == "probe" else frames_total
            stage_id = _start_stage(conn, job, stage_name, stage_frames)
            stage_started = time.monotonic()
            gpu_samples: list[dict[str, Any]] = []
            steps = 1 if stage_name == "probe" else 10
            for step in range(1, steps + 1):
                job = get_job(conn, job_id) or job
                if int(job.get("cancel_requested") or 0):
                    _finish_stage(conn, stage_id, "cancelled", int(stage_frames * ((step - 1) / steps)), stage_frames, stage_started, gpu_samples)
                    _mark_complete(conn, job_id, "cancelled", job_started)
                    return get_job(conn, job_id) or {}
                frames_processed = stage_frames if steps == 1 else int(round(stage_frames * step / steps))
                gpu_samples.append(read_gpu_snapshot().as_dict())
                _update_progress(conn, job_id, stage_id, stage_name, stage_index, frames_processed, stage_frames)
                stage_elapsed = max(time.monotonic() - stage_started, 0.001)
                stage_fps = frames_processed / stage_elapsed
                observed_remaining = ((stage_frames - frames_processed) / max(stage_fps, 0.001)) + max(
                    0.0, (len(PIPELINE_STAGES) - stage_index - 1) * (frames_total / 30.0)
                )
                live_eta = smooth_eta(live_eta, observed_remaining)
                conn.execute(
                    "UPDATE jobs SET estimated_total_seconds_final = ?, updated_at = ? WHERE id = ?",
                    (live_eta, utc_now(), job_id),
                )
                conn.commit()
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            _finish_stage(conn, stage_id, "complete", stage_frames, stage_frames, stage_started, gpu_samples)
            append_log(conn, job_id, f"Stage complete: {stage_name}.")

        _mark_complete(conn, job_id, "complete", job_started)
        update_performance_profiles(conn, job_id)
        return get_job(conn, job_id) or {}
    except Exception as exc:
        _mark_complete(conn, job_id, "failed", job_started, str(exc))
        raise


def _run_real_job(conn: sqlite3.Connection, job: Mapping[str, Any], settings: Settings, job_started: float) -> dict[str, Any]:
    job_id = int(job["id"])
    log_path = Path(job["log_path"] or settings.data_dir / "logs" / f"job-{job_id}.log")
    options = json.loads(job.get("options_json") or "{}")
    frames_total = max(int(job.get("frames_total") or job.get("source_frame_count") or 1), 1)
    input_path = resolve_managed_path(settings, str(job["input_path"]), "input", must_exist=True)
    output_path = Path(str(job["output_path"]))
    work_dir = settings.data_dir / "work" / f"job-{job_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    preprocess = PreprocessOptions(**(options.get("preprocessing") or {}))
    seedvr2 = SeedVR2Options(**(options.get("seedvr2") or {}))
    encode = EncodeOptions(**(options.get("encode") or {}))
    intermediate_path = work_dir / "preprocessed.mkv"
    upscaled_path = work_dir / "seedvr2-upscaled.mkv"

    try:
        _run_external_stage(conn, job, "probe", 0, 1, lambda: append_log(conn, job_id, "Source metadata is already prepared."))
        _run_external_stage(
            conn,
            job,
            "preprocess",
            1,
            frames_total,
            lambda: _require_success(build_lossless_intermediate_command(settings.ffmpeg_path, input_path, intermediate_path, preprocess), log_path),
        )
        adapter = SeedVR2Adapter(settings.seedvr2_cli_path, settings.seedvr2_model_dir, repo_dir=settings.seedvr2_repo_dir)
        _run_external_stage(
            conn,
            job,
            "upscale",
            2,
            frames_total,
            lambda: adapter.run(
                intermediate_path,
                upscaled_path,
                seedvr2,
                log_path,
                target_width=job.get("target_width"),
                target_height=job.get("target_height"),
            ),
        )
        _run_external_stage(conn, job, "sharpen", 3, frames_total, lambda: append_log(conn, job_id, "No separate sharpen stage configured."))
        _run_external_stage(
            conn,
            job,
            "encode",
            4,
            frames_total,
            lambda: _require_success(build_encode_command(settings.ffmpeg_path, upscaled_path, input_path, output_path, encode), log_path),
        )
        _run_external_stage(conn, job, "mux", 5, frames_total, lambda: append_log(conn, job_id, "Audio mux and metadata sync were handled during encode."))
        _mark_complete(conn, job_id, "complete", job_started)
        update_performance_profiles(conn, job_id)
        return get_job(conn, job_id) or {}
    except Exception as exc:
        _mark_complete(conn, job_id, "failed", job_started, str(exc))
        raise


def _run_external_stage(
    conn: sqlite3.Connection,
    job: Mapping[str, Any],
    stage_name: str,
    stage_index: int,
    frames_total: int,
    action: Any,
) -> None:
    job_id = int(job["id"])
    stage_id = _start_stage(conn, job, stage_name, frames_total)
    stage_started = time.monotonic()
    gpu_samples = [read_gpu_snapshot().as_dict()]
    action()
    gpu_samples.append(read_gpu_snapshot().as_dict())
    _update_progress(conn, job_id, stage_id, stage_name, stage_index, frames_total, frames_total)
    _finish_stage(conn, stage_id, "complete", frames_total, frames_total, stage_started, gpu_samples)
    append_log(conn, job_id, f"Stage complete: {stage_name}.")


def _require_success(command: list[str], log_path: Path) -> None:
    result = run_command(command, log_path)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")


def run_next_job(conn: sqlite3.Connection, settings: Settings, sleep_seconds: float = 0.2) -> int | None:
    job_id = acquire_next_job(conn)
    if job_id is None:
        return None
    run_job(conn, job_id, settings, sleep_seconds=sleep_seconds)
    return job_id
