from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _sqlite_path_from_url(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        return Path(database_url.removeprefix("sqlite:///"))
    if database_url.startswith("sqlite://"):
        raise ValueError("Only filesystem SQLite URLs are supported, for example sqlite:////data/app.db")
    return Path(database_url)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    seedvr2_cli_path: str
    seedvr2_model_dir: Path
    mock_pipeline: bool
    run_in_process_worker: bool
    ffmpeg_path: str
    ffprobe_path: str
    prefer_gpu: bool
    require_gpu_for_real_pipeline: bool

    @property
    def database_path(self) -> Path:
        return _sqlite_path_from_url(self.database_url)


def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'app.db'}")
    return Settings(
        data_dir=data_dir,
        database_url=database_url,
        seedvr2_cli_path=os.getenv("SEEDVR2_CLI_PATH", "/opt/seedvr2/inference_cli.py"),
        seedvr2_model_dir=Path(os.getenv("SEEDVR2_MODEL_DIR", "/models/seedvr2")),
        mock_pipeline=_as_bool(os.getenv("MOCK_PIPELINE"), True),
        run_in_process_worker=_as_bool(os.getenv("RUN_IN_PROCESS_WORKER"), False),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"),
        ffprobe_path=os.getenv("FFPROBE_PATH", "ffprobe"),
        prefer_gpu=_as_bool(os.getenv("PREFER_GPU"), True),
        require_gpu_for_real_pipeline=_as_bool(os.getenv("REQUIRE_GPU_FOR_REAL_PIPELINE"), True),
    )
