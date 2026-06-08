from __future__ import annotations

from pathlib import Path

from app.jobs import create_job, get_stage_stats, run_job


def test_job_state_machine_runs_mock_pipeline_to_completion(conn, settings):
    job = create_job(
        conn,
        settings,
        {
            "input_path": "sample.mkv",
            "preset": "Progressive",
            "source_metadata": {
                "filename": "sample.mkv",
                "duration_seconds": 10.0,
                "frame_count_estimate": 24,
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

    finished = run_job(conn, job["id"], settings, sleep_seconds=0)
    stages = get_stage_stats(conn, job["id"])

    assert finished["status"] == "complete"
    assert finished["progress"] == 1
    assert len(stages) == 6
    assert {stage["status"] for stage in stages} == {"complete"}


def test_job_uses_selected_output_container(conn, settings):
    job = create_job(
        conn,
        settings,
        {
            "input_path": "sample.mov",
            "preset": "Progressive",
            "source_metadata": {
                "filename": "sample.mov",
                "duration_seconds": 1.0,
                "frame_count_estimate": 12,
                "width": 640,
                "height": 360,
                "frame_rate": 24.0,
                "scan_type": "progressive",
                "audio_streams": [],
                "video_codec": "h264",
            },
            "target": {"mode": "keep"},
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
            "encode": {
                "codec": "h265",
                "hardware": "auto",
                "container": "mp4",
                "quality": 20,
                "preset": "medium",
                "copy_audio": True,
                "audio_mode": "copy",
                "audio_bitrate": "192k",
            },
        },
    )

    assert job["output_path"].endswith("sample_restored.mp4")


def test_job_uses_selected_output_path(conn, settings):
    job = create_job(
        conn,
        settings,
        {
            "input_path": "source.mkv",
            "output_path": "output/custom/source_done.mov",
            "source_metadata": {
                "filename": "source.mkv",
                "duration_seconds": 1.0,
                "frame_count_estimate": 12,
                "width": 640,
                "height": 360,
                "frame_rate": 24.0,
                "scan_type": "progressive",
                "audio_streams": [],
                "video_codec": "h264",
            },
            "encode": {"container": "mov", "hardware": "cpu", "codec": "h264"},
        },
    )

    expected = (settings.data_dir / "output" / "custom" / "source_done.mov").resolve()
    assert Path(job["output_path"]) == expected
    assert expected.parent.exists()
