from __future__ import annotations

import subprocess
from pathlib import Path

from ..schemas import PreprocessOptions


def build_preprocess_filters(options: PreprocessOptions | dict[str, str]) -> list[str]:
    data = options if isinstance(options, dict) else options.model_dump()
    filters: list[str] = []
    if data.get("deinterlace") == "bwdif":
        filters.append("bwdif=mode=send_frame:parity=auto:deint=all")
    if data.get("inverse_telecine") in {"auto", "force_23_976"}:
        filters.append("fieldmatch")
        filters.append("decimate")
    denoise = data.get("denoise")
    if denoise in {"light", "medium", "heavy"}:
        strength = {"light": "1.5:1.5:3:3", "medium": "2:2:5:5", "heavy": "3:3:7:7"}[denoise]
        filters.append(f"hqdn3d={strength}")
    deblock = data.get("deblock")
    if deblock in {"light", "medium"}:
        filters.append("deblock=filter=weak:block=8" if deblock == "light" else "deblock=filter=strong:block=8")
    return filters


def build_lossless_intermediate_command(
    ffmpeg_path: str,
    input_path: Path,
    output_path: Path,
    options: PreprocessOptions,
) -> list[str]:
    command = [ffmpeg_path, "-y", "-i", str(input_path)]
    filters = build_preprocess_filters(options)
    if filters:
        command.extend(["-vf", ",".join(filters)])
    command.extend(["-c:v", "ffv1", "-level", "3", "-g", "1", "-an", str(output_path)])
    return command


def run_command(command: list[str], log_file: Path) -> subprocess.CompletedProcess[str]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(command) + "\n")
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, text=True, check=False)
    return result

