from __future__ import annotations

import shutil


def vapoursynth_available() -> bool:
    return shutil.which("vspipe") is not None


def qtgmc_setup_message() -> str:
    if vapoursynth_available():
        return "VapourSynth vspipe is available; QTGMC scripts can be mounted into the container."
    return "VapourSynth/QTGMC is optional in this MVP. Use FFmpeg bwdif until vspipe and QTGMC plugins are mounted."

