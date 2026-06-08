from __future__ import annotations

from app.jobs import create_job, run_job
from app.pipeline.stats import update_performance_profiles


def test_performance_stats_aggregation_creates_profiles(conn, settings):
    job = create_job(
        conn,
        settings,
        {
            "input_path": "sample.mkv",
            "preset": "Progressive",
            "source_metadata": {
                "filename": "sample.mkv",
                "duration_seconds": 2.0,
                "frame_count_estimate": 12,
                "width": 640,
                "height": 360,
                "frame_rate": 24.0,
                "scan_type": "progressive",
                "audio_streams": [],
                "video_codec": "h264",
            },
            "target": {"mode": "720p"},
            "preprocessing": {"deinterlace": "none", "inverse_telecine": "off", "denoise": "off", "deblock": "off"},
            "seedvr2": {
                "model": "3B",
                "custom_model_path": None,
                "precision": "auto",
                "batch_size": 5,
                "temporal_overlap": 2,
                "vae_tiling": True,
                "blockswap": False,
                "colour_correction": True,
            },
            "encode": {"codec": "h265", "hardware": "nvenc", "quality": 20, "preset": "medium", "copy_audio": True},
        },
    )
    run_job(conn, job["id"], settings, sleep_seconds=0)
    update_performance_profiles(conn, job["id"])

    profiles = conn.execute("SELECT * FROM performance_profiles").fetchall()

    assert len(profiles) >= 6
    assert {profile["stage_name"] for profile in profiles} >= {"probe", "upscale", "encode"}

