from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .config import Settings
from .gpu import read_gpu_snapshot
from .pipeline.seedvr2 import SeedVR2Adapter, SeedVR2Unavailable
from .schemas import ModelTestRequest, SeedVR2Options


MODEL_FILE_EXTENSIONS = {".bin", ".ckpt", ".gguf", ".json", ".model", ".pt", ".pth", ".safetensors"}


def _model_path(settings: Settings, model: str, custom_model_path: str | None = None) -> Path:
    if model == "custom":
        if not custom_model_path:
            raise ValueError("Custom model path is required for model='custom'")
        return Path(custom_model_path)
    return settings.seedvr2_model_dir / model


def _directory_summary(path: Path) -> dict[str, Any]:
    if path.is_file():
        return {
            "exists": True,
            "path": str(path),
            "file_count": 1,
            "model_file_count": 1 if path.suffix.lower() in MODEL_FILE_EXTENSIONS else 0,
            "size_bytes": path.stat().st_size,
        }
    if not path.exists():
        return {"exists": False, "path": str(path), "file_count": 0, "model_file_count": 0, "size_bytes": 0}
    files = [candidate for candidate in path.rglob("*") if candidate.is_file()]
    model_files = [candidate for candidate in files if candidate.suffix.lower() in MODEL_FILE_EXTENSIONS]
    return {
        "exists": True,
        "path": str(path),
        "file_count": len(files),
        "model_file_count": len(model_files),
        "size_bytes": sum(candidate.stat().st_size for candidate in files),
    }


def inspect_seedvr2_environment(settings: Settings) -> dict[str, Any]:
    gpu = read_gpu_snapshot().as_dict()
    cli_path = Path(settings.seedvr2_cli_path)
    entrypoints = _entrypoints(settings)
    cli_exists = cli_path.exists() or any(item["exists"] for item in entrypoints)
    models = [_model_summary(settings, "3B"), _model_summary(settings, "7B")]
    return {
        "ok": bool(gpu.get("available")) and cli_exists and any(model["ready"] for model in models),
        "gpu": gpu,
        "cli": {"path": str(cli_path), "exists": cli_exists, "entrypoints": entrypoints, "repo_dir": str(settings.seedvr2_repo_dir)},
        "model_dir": str(settings.seedvr2_model_dir),
        "models": models,
        "mock_pipeline": settings.mock_pipeline,
        "message": _readiness_message(gpu, cli_exists, models),
    }


def _model_summary(settings: Settings, model: str) -> dict[str, Any]:
    summary = _directory_summary(_model_path(settings, model))
    ready = bool(summary["exists"] and summary["model_file_count"] > 0)
    return {"name": model, "ready": ready, **summary}


def _readiness_message(gpu: dict[str, Any], cli_exists: bool, models: list[dict[str, Any]]) -> str:
    if not gpu.get("available"):
        return "GPU is not visible to this container yet."
    if not cli_exists:
        return "SeedVR2 CLI is not mounted/configured yet."
    if not any(model["ready"] for model in models):
        return "No SeedVR2 model files were found under the configured model directory."
    return "GPU, CLI, and at least one model directory look ready."


def _entrypoints(settings: Settings) -> list[dict[str, Any]]:
    return [
        {
            "model": "3B",
            "path": str(settings.seedvr2_repo_dir / "projects" / "inference_seedvr2_3b.py"),
            "exists": (settings.seedvr2_repo_dir / "projects" / "inference_seedvr2_3b.py").exists(),
        },
        {
            "model": "7B",
            "path": str(settings.seedvr2_repo_dir / "projects" / "inference_seedvr2_7b.py"),
            "exists": (settings.seedvr2_repo_dir / "projects" / "inference_seedvr2_7b.py").exists(),
        },
    ]


def prepare_model_test_clip(settings: Settings) -> Path:
    work_dir = settings.data_dir / "work" / "model-check"
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / "seedvr2-smoke-input.mp4"
    if input_path.exists():
        return input_path
    command = [
        settings.ffmpeg_path,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=128x128:rate=2",
        "-t",
        "1",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        str(input_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Could not create SeedVR2 smoke-test input with FFmpeg")
    return input_path


def test_seedvr2_model(settings: Settings, request: ModelTestRequest) -> dict[str, Any]:
    gpu = read_gpu_snapshot().as_dict()
    model_path = _model_path(settings, request.model, request.custom_model_path)
    model_summary = _directory_summary(model_path)
    adapter = SeedVR2Adapter(settings.seedvr2_cli_path, settings.seedvr2_model_dir, repo_dir=settings.seedvr2_repo_dir)
    work_dir = settings.data_dir / "work" / "model-check"
    output_path = work_dir / "seedvr2-smoke-output.mkv"
    log_path = settings.data_dir / "logs" / "model-check.log"
    options = SeedVR2Options(
        model=request.model,
        custom_model_path=request.custom_model_path,
        precision=request.precision,
        batch_size=request.batch_size,
        temporal_overlap=request.temporal_overlap,
        vae_tiling=True,
        blockswap=False,
        colour_correction=True,
    )

    input_path: Path | None = None
    command: list[str] | None = None
    try:
        input_path = prepare_model_test_clip(settings)
        command = adapter.build_command(input_path, output_path, options, target_width=128, target_height=128)
    except SeedVR2Unavailable as exc:
        return _model_test_result(False, "cli_missing", str(exc), gpu, model_summary, input_path, command, False, log_path)
    except Exception as exc:
        return _model_test_result(False, "setup_failed", str(exc), gpu, model_summary, input_path, command, False, log_path)

    if not gpu.get("available"):
        return _model_test_result(False, "gpu_missing", "GPU is not visible; SeedVR2 should not be run on CPU for this workbench.", gpu, model_summary, input_path, command, False, log_path)
    if not model_summary["exists"] or model_summary["model_file_count"] == 0:
        return _model_test_result(False, "model_missing", f"Model files were not found at {model_path}.", gpu, model_summary, input_path, command, False, log_path)
    if not request.run_inference:
        return _model_test_result(True, "dry_run_ready", "Prepared a tiny input clip and built the SeedVR2 command. Enable live inference to prove the CLI accepts input end to end.", gpu, model_summary, input_path, command, False, log_path)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(command) + "\n")
        result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, text=True, timeout=request.timeout_seconds, check=False)
    ok = result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
    return _model_test_result(
        ok,
        "inference_passed" if ok else "inference_failed",
        "SeedVR2 accepted the smoke-test clip and produced output." if ok else f"SeedVR2 exited with code {result.returncode}. See model-check.log.",
        gpu,
        model_summary,
        input_path,
        command,
        True,
        log_path,
        output_path,
    )


def _model_test_result(
    ok: bool,
    status: str,
    message: str,
    gpu: dict[str, Any],
    model_summary: dict[str, Any],
    input_path: Path | None,
    command: list[str] | None,
    inference_ran: bool,
    log_path: Path,
    output_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "message": message,
        "gpu": gpu,
        "model": model_summary,
        "prepared_input_path": str(input_path) if input_path else None,
        "output_path": str(output_path) if output_path else None,
        "command": command,
        "inference_ran": inference_ran,
        "log_path": str(log_path),
        "nvidia_smi_path": shutil.which("nvidia-smi"),
    }
