from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..schemas import SeedVR2Options


class SeedVR2Unavailable(RuntimeError):
    pass


@dataclass
class SeedVR2Adapter:
    cli_path: str
    model_dir: Path

    def is_available(self) -> bool:
        return Path(self.cli_path).exists()

    def build_command(self, input_path: Path, output_path: Path, options: SeedVR2Options) -> list[str]:
        if not self.is_available():
            raise SeedVR2Unavailable(
                f"SeedVR2 CLI was not found at {self.cli_path}. Set SEEDVR2_CLI_PATH or enable MOCK_PIPELINE."
            )
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

    def run(self, input_path: Path, output_path: Path, options: SeedVR2Options, log_file: Path, timeout_seconds: int | None = None) -> None:
        command = self.build_command(input_path, output_path, options)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write("$ " + " ".join(command) + "\n")
            result = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, text=True, check=False, timeout=timeout_seconds)
        if result.returncode != 0:
            raise RuntimeError(f"SeedVR2 failed with exit code {result.returncode}")


class MockSeedVR2Runner:
    def run(self, input_path: Path, output_path: Path, options: SeedVR2Options, log_file: Path) -> None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(
                "Mock SeedVR2 runner used. Mount the real repository and set SEEDVR2_CLI_PATH "
                "to perform actual upscaling.\n"
            )
