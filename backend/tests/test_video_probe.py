from __future__ import annotations

import json
from pathlib import Path

from app.video_probe import parse_ffprobe


def test_ffprobe_parser_extracts_video_and_audio_metadata():
    payload = json.loads((Path(__file__).parent / "fixtures" / "ffprobe_sample.json").read_text(encoding="utf-8"))

    metadata = parse_ffprobe(payload, "/data/input/sample.vob")

    assert metadata.filename == "sample.vob"
    assert metadata.width == 720
    assert metadata.height == 480
    assert round(metadata.frame_rate or 0, 3) == 29.97
    assert metadata.frame_count_estimate == 1800
    assert metadata.scan_type == "interlaced (tt)"
    assert metadata.audio_streams[0].codec == "ac3"
    assert metadata.video_codec == "mpeg2video"

