from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import connect, init_db, row_to_dict
from .eta import estimate_job
from .gpu import read_gpu_snapshot
from .jobs import cancel_job, create_job, get_job, get_stage_stats, list_jobs, read_logs, run_job
from .model_check import inspect_seedvr2_environment, test_seedvr2_model
from .schemas import JobCreate, ModelTestRequest, ProbeRequest
from .video_probe import list_input_files, run_ffprobe, safe_data_path, save_uploaded_video

settings = get_settings()
app = FastAPI(title="SeedVR2 Video Workbench API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def db_session():
    conn = connect(settings)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def startup() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    for child in ("input", "output", "work", "logs"):
        (settings.data_dir / child).mkdir(parents=True, exist_ok=True)
    with db_session():
        pass


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "data_dir": str(settings.data_dir),
        "database": str(settings.database_path),
        "gpu": read_gpu_snapshot().as_dict(),
    }


@app.get("/api/settings")
def api_settings() -> dict[str, Any]:
    return {
        "data_dir": str(settings.data_dir),
        "seedvr2_cli_path": settings.seedvr2_cli_path,
        "seedvr2_model_dir": str(settings.seedvr2_model_dir),
        "mock_pipeline": settings.mock_pipeline,
        "run_in_process_worker": settings.run_in_process_worker,
        "prefer_gpu": settings.prefer_gpu,
        "require_gpu_for_real_pipeline": settings.require_gpu_for_real_pipeline,
        "ffmpeg_path": settings.ffmpeg_path,
        "ffprobe_path": settings.ffprobe_path,
    }


@app.post("/api/probe")
def probe(request: ProbeRequest) -> dict[str, Any]:
    try:
        path = safe_data_path(settings.data_dir, request.input_path, "input")
        metadata = run_ffprobe(path, settings.ffprobe_path)
        return _dump_model(metadata)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/files/input")
def input_files() -> list[dict[str, Any]]:
    return list_input_files(settings.data_dir)


@app.post("/api/files/input/upload")
def upload_input_file(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        return save_uploaded_video(settings.data_dir, file.filename or "", file.file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/models")
def models() -> dict[str, Any]:
    return inspect_seedvr2_environment(settings)


@app.post("/api/models/test")
def test_model(request: ModelTestRequest) -> dict[str, Any]:
    return test_seedvr2_model(settings, request)


@app.get("/api/jobs")
def jobs() -> list[dict[str, Any]]:
    with db_session() as conn:
        return list_jobs(conn)


@app.post("/api/jobs")
def post_job(request: JobCreate) -> dict[str, Any]:
    with db_session() as conn:
        job = create_job(conn, settings, request)
    if settings.run_in_process_worker:
        thread = threading.Thread(target=_run_job_background, args=(int(job["id"]),), daemon=True)
        thread.start()
    return job


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int) -> dict[str, Any]:
    with db_session() as conn:
        job = get_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job["stages"] = get_stage_stats(conn, job_id)
        return job


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: int) -> dict[str, Any]:
    with db_session() as conn:
        job = cancel_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job


@app.get("/api/jobs/{job_id}/logs")
def logs(job_id: int) -> dict[str, str]:
    with db_session() as conn:
        if not get_job(conn, job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        return {"text": read_logs(conn, job_id)}


@app.get("/api/jobs/{job_id}/eta")
def eta(job_id: int) -> dict[str, Any]:
    with db_session() as conn:
        job = get_job(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return estimate_job(conn, job)


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    with db_session() as conn:
        totals = row_to_dict(
            conn.execute(
                """
                SELECT
                  COUNT(*) AS jobs_total,
                  SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) AS jobs_complete,
                  AVG(total_elapsed_seconds) AS average_elapsed_seconds
                FROM jobs
                """
            ).fetchone()
        )
        stages = [
            row_to_dict(row) or {}
            for row in conn.execute(
                """
                SELECT stage_name, COUNT(*) AS sample_count, AVG(effective_fps) AS average_fps
                FROM job_stage_stats
                WHERE completed_sample = 1
                GROUP BY stage_name
                ORDER BY stage_name
                """
            ).fetchall()
        ]
        eta_accuracy = [
            row_to_dict(row) or {}
            for row in conn.execute(
                """
                SELECT id, preset, estimated_total_seconds_initial, estimated_total_seconds_final,
                       total_elapsed_seconds,
                       CASE
                         WHEN total_elapsed_seconds > 0 AND estimated_total_seconds_initial IS NOT NULL
                         THEN ABS(estimated_total_seconds_initial - total_elapsed_seconds) / total_elapsed_seconds * 100
                       END AS initial_error_percent,
                       CASE
                         WHEN total_elapsed_seconds > 0 AND estimated_total_seconds_final IS NOT NULL
                         THEN ABS(estimated_total_seconds_final - total_elapsed_seconds) / total_elapsed_seconds * 100
                       END AS final_error_percent
                FROM jobs
                WHERE status = 'complete'
                ORDER BY id DESC
                LIMIT 50
                """
            ).fetchall()
        ]
        return {"totals": totals, "stage_throughput": stages, "eta_accuracy": eta_accuracy}


@app.get("/api/stats/performance-profiles")
def performance_profiles() -> list[dict[str, Any]]:
    with db_session() as conn:
        return [
            row_to_dict(row) or {}
            for row in conn.execute("SELECT * FROM performance_profiles ORDER BY last_updated_at DESC, id DESC").fetchall()
        ]


def _run_job_background(job_id: int) -> None:
    with db_session() as conn:
        run_job(conn, job_id, settings)


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
