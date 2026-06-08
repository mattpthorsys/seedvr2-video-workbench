from __future__ import annotations

import json
import sqlite3
from statistics import mean, median
from typing import Any

from ..db import utc_now


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
    return ordered[index]


def update_performance_profiles(conn: sqlite3.Connection, job_id: int) -> None:
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        return
    stage_rows = conn.execute(
        """
        SELECT DISTINCT stage_name
        FROM job_stage_stats
        WHERE job_id = ? AND status = 'complete' AND completed_sample = 1 AND effective_fps > 0
        """,
        (job_id,),
    ).fetchall()
    for stage in stage_rows:
        stage_name = stage["stage_name"]
        samples = conn.execute(
            """
            SELECT s.effective_fps
            FROM job_stage_stats s
            JOIN jobs j ON j.id = s.job_id
            WHERE s.stage_name = ?
              AND s.status = 'complete'
              AND s.completed_sample = 1
              AND s.effective_fps > 0
              AND COALESCE(j.preset, '') = COALESCE(?, '')
              AND COALESCE(j.source_width, 0) = COALESCE(?, 0)
              AND COALESCE(j.source_height, 0) = COALESCE(?, 0)
              AND COALESCE(j.target_width, 0) = COALESCE(?, 0)
              AND COALESCE(j.target_height, 0) = COALESCE(?, 0)
              AND COALESCE(j.seedvr2_model, '') = COALESCE(?, '')
              AND COALESCE(j.seedvr2_precision, '') = COALESCE(?, '')
              AND COALESCE(j.batch_size, 0) = COALESCE(?, 0)
              AND COALESCE(j.temporal_overlap, -1) = COALESCE(?, -1)
              AND COALESCE(j.encoder, '') = COALESCE(?, '')
              AND COALESCE(j.gpu_name, '') = COALESCE(?, '')
            """,
            (
                stage_name,
                job["preset"],
                job["source_width"],
                job["source_height"],
                job["target_width"],
                job["target_height"],
                job["seedvr2_model"],
                job["seedvr2_precision"],
                job["batch_size"],
                job["temporal_overlap"],
                job["encoder"],
                job["gpu_name"],
            ),
        ).fetchall()
        fps_values = [float(row["effective_fps"]) for row in samples]
        if not fps_values:
            continue
        conn.execute(
            """
            INSERT INTO performance_profiles (
              stage_name, source_type, preset, source_width, source_height, target_width, target_height,
              model, precision, batch_size, temporal_overlap, encoder, gpu_name, sample_count,
              mean_fps, median_fps, p20_fps, p80_fps, mean_seconds_per_frame, last_updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stage_name,
                _source_type(job["options_json"]),
                job["preset"],
                job["source_width"],
                job["source_height"],
                job["target_width"],
                job["target_height"],
                job["seedvr2_model"],
                job["seedvr2_precision"],
                job["batch_size"],
                job["temporal_overlap"],
                job["encoder"],
                job["gpu_name"],
                len(fps_values),
                mean(fps_values),
                median(fps_values),
                _percentile(fps_values, 0.2),
                _percentile(fps_values, 0.8),
                1.0 / mean(fps_values),
                utc_now(),
            ),
        )
    conn.commit()


def _source_type(options_json: str | None) -> str | None:
    if not options_json:
        return None
    try:
        options: dict[str, Any] = json.loads(options_json)
    except json.JSONDecodeError:
        return None
    return options.get("preset") or options.get("source_type")
