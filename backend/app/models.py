from __future__ import annotations

JOB_STATUSES = {"queued", "running", "complete", "failed", "cancelled"}
TERMINAL_JOB_STATUSES = {"complete", "failed", "cancelled"}

PIPELINE_STAGES = ["probe", "preprocess", "upscale", "sharpen", "encode", "mux"]

DEFAULT_PRESETS = [
    "Progressive",
    "Interlaced video",
    "Telecined/DVD",
    "PAL DVD/TV",
    "Heavy compression",
    "Soft low-resolution source",
    "Custom",
]

