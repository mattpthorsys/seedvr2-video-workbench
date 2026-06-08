from __future__ import annotations

from pathlib import Path

import pytest

from app.file_browser import browse_directory, browse_roots, resolve_managed_path


def test_browse_directory_returns_rooted_file_picker_items(settings):
    input_dir = settings.data_dir / "input"
    input_dir.mkdir(parents=True)
    video = input_dir / "sample.MP4"
    video.write_bytes(b"video")
    note = input_dir / "readme.txt"
    note.write_text("not a video", encoding="utf-8")

    data_root = next(root for root in browse_roots(settings) if root["label"] == "Data")
    listing = browse_directory(settings, data_root["id"], "input")

    assert listing["root_id"] == data_root["id"]
    assert listing["root_label"] == "Data"
    assert listing["current_path"] == "input"
    assert listing["current_select_path"] == str(input_dir.resolve())
    assert listing["parent_path"] == ""
    assert listing["roots"]
    files_by_name = {item["name"]: item for item in listing["files"]}
    assert files_by_name["readme.txt"]["select_path"] == str(note.resolve())
    assert {name: item["is_video"] for name, item in files_by_name.items()} == {"readme.txt": False, "sample.MP4": True}


def test_resolve_managed_path_allows_configured_roots_and_blocks_escape(settings):
    external_root = Path(settings.browse_roots[-1])
    external_root.mkdir(parents=True)
    external_video = external_root / "camera-roll.mov"
    external_video.write_bytes(b"video")

    assert resolve_managed_path(settings, "clip.mkv", "input") == (settings.data_dir / "input" / "clip.mkv").resolve()
    assert resolve_managed_path(settings, str(external_video), "input", must_exist=True) == external_video.resolve()

    with pytest.raises(ValueError, match="outside configured browse roots|must stay under"):
        resolve_managed_path(settings, str(settings.data_dir / ".." / "escape.mov"), "input")
