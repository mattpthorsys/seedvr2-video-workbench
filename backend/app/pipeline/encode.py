from __future__ import annotations

from pathlib import Path

from ..schemas import EncodeOptions


def _codec_args(options: EncodeOptions) -> list[str]:
    if options.codec == "h264":
        return ["-c:v", "h264_nvenc" if options.hardware == "nvenc" else "libx264"]
    if options.codec == "h265":
        return ["-c:v", "hevc_nvenc" if options.hardware == "nvenc" else "libx265"]
    if options.codec == "av1":
        return ["-c:v", "av1_nvenc" if options.hardware == "nvenc" else "libaom-av1"]
    return ["-c:v", "libx264"]


def _audio_args(options: EncodeOptions) -> list[str]:
    if not options.copy_audio or options.audio_mode == "none":
        return ["-an"]
    if options.audio_mode == "copy":
        return ["-c:a", "copy"]
    if options.audio_mode == "opus":
        return ["-c:a", "libopus", "-b:a", options.audio_bitrate]
    return ["-c:a", "aac", "-b:a", options.audio_bitrate, "-af", "aresample=async=1:first_pts=0"]


def build_encode_command(
    ffmpeg_path: str,
    upscaled_video: Path,
    original_input: Path,
    output_path: Path,
    options: EncodeOptions,
) -> list[str]:
    command = [
        ffmpeg_path,
        "-y",
        "-fflags",
        "+genpts",
        "-i",
        str(upscaled_video),
    ]
    if options.copy_audio:
        command.extend(["-i", str(original_input), "-map", "0:v:0", "-map", "1:a?", "-map_metadata", "1", "-map_chapters", "1"])
    else:
        command.extend(["-map", "0:v:0"])
    command.extend(_codec_args(options))
    command.extend(_audio_args(options))
    if options.hardware == "nvenc":
        command.extend(["-cq", str(options.quality), "-preset", options.preset])
    else:
        command.extend(["-crf", str(options.quality), "-preset", options.preset])
    command.extend(["-avoid_negative_ts", "make_zero", "-max_interleave_delta", "0", "-shortest"])
    if options.container in {"mp4", "mov"}:
        command.extend(["-movflags", "+faststart"])
    command.append(str(output_path))
    return command
