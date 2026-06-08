from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.db import connect, init_db


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    return Settings(
        data_dir=data_dir,
        database_url=f"sqlite:///{data_dir / 'app.db'}",
        seedvr2_cli_path="/opt/seedvr2/inference_cli.py",
        seedvr2_model_dir=tmp_path / "models",
        mock_pipeline=True,
        run_in_process_worker=False,
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        prefer_gpu=False,
        require_gpu_for_real_pipeline=False,
        browse_roots=(data_dir, tmp_path / "models"),
    )


@pytest.fixture()
def conn(settings: Settings):
    database = connect(settings)
    init_db(database)
    try:
        yield database
    finally:
        database.close()
