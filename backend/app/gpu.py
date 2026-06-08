from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class GpuSnapshot:
    name: str | None = None
    driver_version: str | None = None
    cuda_version: str | None = None
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    utilisation_percent: float | None = None
    temperature_c: float | None = None
    available: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "name": self.name,
            "driver_version": self.driver_version,
            "cuda_version": self.cuda_version,
            "memory_used_mb": self.memory_used_mb,
            "memory_total_mb": self.memory_total_mb,
            "utilisation_percent": self.utilisation_percent,
            "temperature_c": self.temperature_c,
        }


def _to_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None


def read_gpu_snapshot() -> GpuSnapshot:
    if shutil.which("nvidia-smi") is None:
        return GpuSnapshot(available=False)
    query = (
        "name,driver_version,memory.used,memory.total,"
        "utilization.gpu,temperature.gpu"
    )
    result = subprocess.run(
        ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return GpuSnapshot(available=False)
    first = result.stdout.strip().splitlines()[0]
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 6:
        return GpuSnapshot(available=False)

    cuda_version = None
    try:
        raw_result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if raw_result.returncode == 0:
            import re
            m = re.search(r"CUDA Version:\s*([\d\.]+)", raw_result.stdout)
            if m:
                cuda_version = m.group(1)
    except Exception:
        pass

    return GpuSnapshot(
        name=parts[0],
        driver_version=parts[1],
        cuda_version=cuda_version,
        memory_used_mb=_to_float(parts[2]),
        memory_total_mb=_to_float(parts[3]),
        utilisation_percent=_to_float(parts[4]),
        temperature_c=_to_float(parts[5]),
        available=True,
    )

