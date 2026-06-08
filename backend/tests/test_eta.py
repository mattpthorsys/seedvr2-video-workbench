from __future__ import annotations

from app.eta import estimate_job, smooth_eta


def test_eta_with_no_history_uses_low_confidence_defaults(conn):
    estimate = estimate_job(
        conn,
        {
            "source_frame_count": 120,
            "source_width": 720,
            "source_height": 480,
            "target_width": 1920,
            "target_height": 1080,
        },
    )

    assert estimate["confidence"] == "low"
    assert estimate["samples_used"] == 0
    assert estimate["estimated_total_seconds"] > 0
    assert estimate["estimated_stage_seconds"][2]["stage_name"] == "upscale"
    assert estimate["estimated_stage_seconds"][2]["basis"] == "conservative default"


def test_eta_with_matching_history_uses_weighted_profile(conn):
    conn.execute(
        """
        INSERT INTO performance_profiles (
          stage_name, preset, source_width, source_height, target_width, target_height,
          model, precision, batch_size, temporal_overlap, encoder, gpu_name, sample_count,
          mean_fps, median_fps, p20_fps, p80_fps, mean_seconds_per_frame, last_updated_at
        ) VALUES (
          'upscale', 'Progressive', 720, 480, 1920, 1080,
          '3B', 'auto', 5, 2, 'h265', 'RTX 5060 Ti', 8,
          2.0, 2.0, 1.8, 2.2, 0.5, '2026-06-08T00:00:00+00:00'
        )
        """
    )
    conn.commit()

    estimate = estimate_job(
        conn,
        {
            "source_frame_count": 100,
            "source_width": 720,
            "source_height": 480,
            "target_width": 1920,
            "target_height": 1080,
            "preset": "Progressive",
            "seedvr2_model": "3B",
            "seedvr2_precision": "auto",
            "batch_size": 5,
            "temporal_overlap": 2,
            "encoder": "h265",
            "gpu_name": "RTX 5060 Ti",
        },
    )

    upscale = next(stage for stage in estimate["estimated_stage_seconds"] if stage["stage_name"] == "upscale")
    assert estimate["confidence"] == "medium"
    assert upscale["basis"] == "historical profile"
    assert upscale["estimated_seconds"] == 50.0


def test_eta_smoothing_dampens_large_live_changes():
    assert smooth_eta(None, 100) == 100
    assert smooth_eta(100, 20, alpha=0.25) == 80
    assert smooth_eta(80, 120, alpha=0.5) == 100

