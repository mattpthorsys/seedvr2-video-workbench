from __future__ import annotations

from pathlib import Path

from app.pipeline.encode import build_encode_command
from app.schemas import EncodeOptions


def test_encode_command_maps_original_audio_and_sync_options():
    command = build_encode_command(
        "ffmpeg",
        Path("/data/work/upscaled.mkv"),
        Path("/data/input/source.vob"),
        Path("/data/output/source_restored.mp4"),
        EncodeOptions(codec="h265", hardware="nvenc", container="mp4", audio_mode="copy", copy_audio=True),
    )

    assert "-map" in command
    assert "0:v:0" in command
    assert "1:a?" in command
    assert "-c:a" in command
    assert "copy" in command
    assert "-avoid_negative_ts" in command
    assert "-shortest" in command
    assert "+faststart" in command


def test_encode_command_can_disable_audio():
    command = build_encode_command(
        "ffmpeg",
        Path("/data/work/upscaled.mkv"),
        Path("/data/input/source.mkv"),
        Path("/data/output/source_restored.webm"),
        EncodeOptions(codec="av1", hardware="cpu", container="webm", audio_mode="none", copy_audio=False),
    )

    assert "-an" in command
    assert "1:a?" not in command
