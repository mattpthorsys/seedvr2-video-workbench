from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, BinaryIO

from .schemas import AudioStream, VideoMetadata


VIDEO_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".asf",
    ".avi",
    ".divx",
    ".dv",
    ".f4v",
    ".flv",
    ".m2ts",
    ".m2v",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".mxf",
    ".ogm",
    ".ogv",
    ".rm",
    ".rmvb",
    ".ts",
    ".vob",
    ".webm",
    ".wmv",
}


def parse_fraction(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return None
    numerator, denominator = value.split("/", 1)
    try:
        bottom = float(denominator)
        if bottom == 0:
            return None
        return float(numerator) / bottom
    except ValueError:
        return None


def _duration(payload: dict[str, Any], video_stream: dict[str, Any] | None) -> float | None:
    for candidate in (
        (payload.get("format") or {}).get("duration"),
        (video_stream or {}).get("duration"),
    ):
        if candidate is None:
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            pass
    return None


def _scan_type(field_order: str | None) -> str:
    if not field_order:
        return "unknown"
    normalised = field_order.lower()
    if normalised in {"progressive", "prog"}:
        return "progressive"
    if normalised in {"tt", "bb", "tb", "bt"}:
        return f"interlaced ({normalised})"
    return normalised


def parse_ffprobe(payload: dict[str, Any], filename: str) -> VideoMetadata:
    streams = payload.get("streams") or []
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio_streams = [
        AudioStream(
            index=int(stream.get("index", 0)),
            codec=stream.get("codec_name"),
            channels=stream.get("channels"),
            language=(stream.get("tags") or {}).get("language"),
        )
        for stream in streams
        if stream.get("codec_type") == "audio"
    ]

    fps = parse_fraction((video_stream or {}).get("avg_frame_rate")) or parse_fraction((video_stream or {}).get("r_frame_rate"))
    duration_seconds = _duration(payload, video_stream)
    frame_count: int | None = None
    if video_stream and video_stream.get("nb_frames"):
        try:
            frame_count = int(video_stream["nb_frames"])
        except ValueError:
            frame_count = None
    if frame_count is None and duration_seconds and fps:
        frame_count = int(round(duration_seconds * fps))

    return VideoMetadata(
        filename=Path(filename).name,
        duration_seconds=duration_seconds,
        frame_count_estimate=frame_count,
        width=(video_stream or {}).get("width"),
        height=(video_stream or {}).get("height"),
        frame_rate=fps,
        scan_type=_scan_type((video_stream or {}).get("field_order")),
        audio_streams=audio_streams,
        video_codec=(video_stream or {}).get("codec_name"),
    )


def run_ffprobe(input_path: Path, ffprobe_path: str = "ffprobe") -> VideoMetadata:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or "ffprobe failed without stderr"
        raise RuntimeError(message)
    return parse_ffprobe(json.loads(result.stdout), str(input_path))


def safe_data_path(data_dir: Path, path_value: str, default_subdir: str = "input") -> Path:
    raw = Path(path_value)
    candidate = raw if raw.is_absolute() else data_dir / default_subdir / raw
    resolved = candidate.resolve()
    data_root = data_dir.resolve()
    if data_root != resolved and data_root not in resolved.parents:
        raise ValueError(f"Path must stay under {data_root}")
    return resolved


def list_input_files(data_dir: Path) -> list[dict[str, Any]]:
    input_dir = data_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for path in sorted(input_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "relative_path": str(path.relative_to(input_dir)),
                    "size_bytes": path.stat().st_size,
                }
            )
    return files


def safe_upload_filename(filename: str) -> str:
    basename = Path(filename).name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", basename)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        raise ValueError("Upload must include a filename")
    if Path(cleaned).suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Unsupported video type: {Path(cleaned).suffix or '(none)'}")
    return cleaned


def save_uploaded_video(data_dir: Path, filename: str, source: BinaryIO) -> dict[str, Any]:
    input_dir = data_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    safe_name = safe_upload_filename(filename)
    target = input_dir / safe_name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 2
        while target.exists():
            target = input_dir / f"{stem}-{counter}{suffix}"
            counter += 1
    with target.open("wb") as destination:
        shutil.copyfileobj(source, destination)
    return {
        "name": target.name,
        "path": str(target),
        "relative_path": str(target.relative_to(input_dir)),
        "size_bytes": target.stat().st_size,
    }
