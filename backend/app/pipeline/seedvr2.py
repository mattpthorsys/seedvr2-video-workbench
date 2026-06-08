from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import copyfile, which

from ..schemas import SeedVR2Options


class SeedVR2Unavailable(RuntimeError):
    pass


@dataclass
class SeedVR2Adapter:
    cli_path: str
    model_dir: Path
    repo_dir: Path | None = None
    torchrun_path: str = "torchrun"

    def is_available(self) -> bool:
        return self._script_path("3B").exists() or Path(self.cli_path).exists()

    def build_command(
        self,
        input_path: Path,
        output_path: Path,
        options: SeedVR2Options,
        target_width: int | None = None,
        target_height: int | None = None,
        sp_size: int = 1,
        seed: int = 42,
    ) -> list[str]:
        script_path = self._script_path(options.model)
        if not script_path.exists():
            legacy_cli = Path(self.cli_path)
            if legacy_cli.exists():
                return self._legacy_command(input_path, output_path, options)
            raise SeedVR2Unavailable(
                f"SeedVR2 inference script was not found at {script_path}. Mount the ByteDance-Seed/SeedVR repo or set SEEDVR2_REPO_DIR."
            )
        if not which(self.torchrun_path):
            raise SeedVR2Unavailable("torchrun was not found. Install the SeedVR environment inside the worker image.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.torchrun_path,
            "--nproc-per-node=1",
            str(script_path),
            "--video_path",
            str(input_path.parent),
            "--output_dir",
            str(output_path.parent),
            "--seed",
            str(seed),
            "--res_h",
            str(target_height or 720),
            "--res_w",
            str(target_width or 1280),
            "--sp_size",
            str(max(sp_size, 1)),
        ]
        return command

    def _legacy_command(self, input_path: Path, output_path: Path, options: SeedVR2Options) -> list[str]:
        model_path = options.custom_model_path if options.model == "custom" else str(self.model_dir / options.model)
        command = [
            "python",
            self.cli_path,
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--model",
            model_path,
            "--precision",
            options.precision,
            "--batch-size",
            str(options.batch_size),
            "--temporal-overlap",
            str(options.temporal_overlap),
        ]
        if options.vae_tiling:
            command.append("--vae-tiling")
        if options.blockswap:
            command.append("--blockswap")
        if options.colour_correction:
            command.append("--colour-correction")
        return command

    def run(
        self,
        input_path: Path,
        output_path: Path,
        options: SeedVR2Options,
        log_file: Path,
        target_width: int | None = None,
        target_height: int | None = None,
        timeout_seconds: int | None = None,
    ) -> Path:
        command = self.build_command(input_path, output_path, options, target_width=target_width, target_height=target_height)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write("$ " + " ".join(command) + "\n")
            result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, text=True, check=False, timeout=timeout_seconds)
        if result.returncode != 0:
            raise RuntimeError(f"SeedVR2 failed with exit code {result.returncode}")
        produced = self._discover_output(output_path)
        if produced != output_path and produced.exists():
            copyfile(produced, output_path)
        return output_path

    def _script_path(self, model: str) -> Path:
        if model == "7B":
            name = "inference_seedvr2_7b.py"
        else:
            name = "inference_seedvr2_3b.py"
        if self.repo_dir:
            return self.repo_dir / "projects" / name
        return Path(self.cli_path)

    @staticmethod
    def _discover_output(expected_path: Path) -> Path:
        if expected_path.exists() and expected_path.stat().st_size > 0:
            return expected_path
        video_exts = {".mkv", ".mp4", ".mov", ".webm", ".avi"}
        candidates = [path for path in expected_path.parent.rglob("*") if path.is_file() and path.suffix.lower() in video_exts]
        if not candidates:
            raise RuntimeError(f"SeedVR2 completed but no output video was found under {expected_path.parent}")
        return max(candidates, key=lambda path: path.stat().st_mtime)


class MockSeedVR2Runner:
    def run(self, input_path: Path, output_path: Path, options: SeedVR2Options, log_file: Path) -> Path:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(
                "Mock SeedVR2 runner used. Mount the real repository and set SEEDVR2_CLI_PATH "
                "to perform actual upscaling.\n"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("mock video placeholder\n", encoding="utf-8")
        return output_path
