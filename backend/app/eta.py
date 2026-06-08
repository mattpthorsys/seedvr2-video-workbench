from __future__ import annotations

import sqlite3
from typing import Any, Mapping

from .models import PIPELINE_STAGES


DEFAULT_STAGE_FPS = {
    "probe": 4000.0,
    "preprocess": 45.0,
    "upscale": 0.65,
    "sharpen": 90.0,
    "encode": 35.0,
    "mux": 200.0,
}


def smooth_eta(previous_seconds: float | None, observed_seconds: float, alpha: float = 0.25) -> float:
    if previous_seconds is None:
        return max(0.0, observed_seconds)
    alpha = min(max(alpha, 0.0), 1.0)
    return max(0.0, previous_seconds * (1.0 - alpha) + observed_seconds * alpha)


def _pixel_delta(row_value: int | None, wanted: int | None) -> float:
    if not row_value or not wanted:
        return 0.35
    return abs(row_value - wanted) / max(row_value, wanted)


def _string_bonus(row_value: str | None, wanted: str | None, bonus: float) -> float:
    if not row_value or not wanted:
        return 0.0
    return bonus if row_value == wanted else 0.0


def _profile_score(row: sqlite3.Row, context: Mapping[str, Any]) -> float:
    source_delta = _pixel_delta(row["source_width"], context.get("source_width")) + _pixel_delta(
        row["source_height"], context.get("source_height")
    )
    target_delta = _pixel_delta(row["target_width"], context.get("target_width")) + _pixel_delta(
        row["target_height"], context.get("target_height")
    )
    score = 1.0 / (1.0 + source_delta + target_delta)
    score += _string_bonus(row["preset"], context.get("preset"), 0.2)
    score += _string_bonus(row["model"], context.get("seedvr2_model"), 0.2)
    score += _string_bonus(row["precision"], context.get("seedvr2_precision"), 0.15)
    score += _string_bonus(row["encoder"], context.get("encoder"), 0.15)
    score += _string_bonus(row["gpu_name"], context.get("gpu_name"), 0.2)
    if row["batch_size"] and context.get("batch_size") and row["batch_size"] == context.get("batch_size"):
        score += 0.1
    if row["temporal_overlap"] is not None and row["temporal_overlap"] == context.get("temporal_overlap"):
        score += 0.05
    return max(score, 0.01)


def _historical_fps(conn: sqlite3.Connection, stage_name: str, context: Mapping[str, Any]) -> tuple[float | None, int]:
    rows = conn.execute(
        """
        SELECT * FROM performance_profiles
        WHERE stage_name = ?
        ORDER BY sample_count DESC, last_updated_at DESC
        LIMIT 30
        """,
        (stage_name,),
    ).fetchall()
    if not rows:
        return None, 0
    weighted_total = 0.0
    weight_sum = 0.0
    sample_count = 0
    for row in rows:
        score = _profile_score(row, context)
        weight = score * max(int(row["sample_count"]), 1)
        weighted_total += float(row["mean_fps"]) * weight
        weight_sum += weight
        sample_count += int(row["sample_count"])
    if weight_sum <= 0:
        return None, 0
    return weighted_total / weight_sum, sample_count


def confidence_for_samples(samples_used: int) -> str:
    if samples_used >= 18:
        return "high"
    if samples_used >= 6:
        return "medium"
    return "low"


def estimate_job(conn: sqlite3.Connection, context: Mapping[str, Any]) -> dict[str, Any]:
    frames = int(context.get("source_frame_count") or context.get("frames_total") or 300)
    frames = max(frames, 1)
    stages: list[dict[str, Any]] = []
    total_seconds = 0.0
    samples_used = 0

    for stage_name in PIPELINE_STAGES:
        historical, samples = _historical_fps(conn, stage_name, context)
        fps = historical or DEFAULT_STAGE_FPS[stage_name]
        basis = "historical profile" if historical else "conservative default"
        seconds = frames / max(fps, 0.001)
        if stage_name == "probe":
            seconds = max(3.0, min(seconds, 30.0))
        if stage_name == "mux":
            seconds = max(5.0, seconds)
        stages.append(
            {
                "stage_name": stage_name,
                "estimated_seconds": round(seconds, 2),
                "fps": round(fps, 4),
                "basis": basis,
            }
        )
        total_seconds += seconds
        samples_used += samples

    confidence = confidence_for_samples(samples_used)
    explanation = (
        f"Estimated {frames} frames across {len(PIPELINE_STAGES)} stages using "
        f"{samples_used} historical samples."
        if samples_used
        else "No matching history yet; using conservative built-in throughput defaults."
    )
    return {
        "estimated_total_seconds": round(total_seconds, 2),
        "estimated_stage_seconds": stages,
        "confidence": confidence,
        "explanation": explanation,
        "samples_used": samples_used,
    }

