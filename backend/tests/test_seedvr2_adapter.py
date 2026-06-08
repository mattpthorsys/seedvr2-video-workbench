from __future__ import annotations

from pathlib import Path

from app.pipeline.seedvr2 import SeedVR2Adapter
from app.schemas import SeedVR2Options


def test_seedvr2_adapter_builds_official_torchrun_command(tmp_path, monkeypatch):
    repo_dir = tmp_path / "seedvr"
    projects = repo_dir / "projects"
    projects.mkdir(parents=True)
    script = projects / "inference_seedvr2_3b.py"
    script.write_text("print('seedvr')", encoding="utf-8")
    monkeypatch.setattr("app.pipeline.seedvr2.which", lambda command: "/usr/bin/torchrun" if command == "torchrun" else None)

    command = SeedVR2Adapter("/legacy.py", tmp_path / "models", repo_dir=repo_dir).build_command(
        tmp_path / "input" / "clip.mkv",
        tmp_path / "output" / "restored.mkv",
        SeedVR2Options(model="3B"),
        target_width=1280,
        target_height=720,
    )

    assert command[:3] == ["torchrun", "--nproc-per-node=1", str(script)]
    assert "--video_path" in command
    assert str(Path(tmp_path / "input")) in command
    assert "--output_dir" in command
    assert str(Path(tmp_path / "output")) in command
    assert "--res_h" in command
    assert "720" in command
    assert "--res_w" in command
    assert "1280" in command
