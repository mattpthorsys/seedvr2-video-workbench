from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings
from .video_probe import VIDEO_EXTENSIONS


DATA_SUBDIRS = {"input", "output", "work", "logs"}


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve()


def browse_roots(settings: Settings) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in (_resolve(settings.data_dir), *[_resolve(path) for path in settings.browse_roots]):
        key = str(root).lower()
        if key in seen:
            continue
        seen.add(key)
        roots.append(
            {
                "id": str(len(roots)),
                "label": _root_label(settings, root),
                "path": str(root),
                "exists": root.exists(),
            }
        )
    return roots


def _root_label(settings: Settings, root: Path) -> str:
    data_dir = _resolve(settings.data_dir)
    model_parent = _resolve(settings.seedvr2_model_dir.parent)
    if root == data_dir:
        return "Data"
    if root == model_parent:
        return "Models"
    return root.name or str(root)


def _root_path(settings: Settings, root_id: str | None) -> Path:
    roots = browse_roots(settings)
    if not roots:
        return _resolve(settings.data_dir)
    if root_id is None:
        return Path(roots[0]["path"])
    for root in roots:
        if root["id"] == str(root_id):
            return Path(root["path"])
    raise ValueError("Unknown browse root")


def _ensure_inside(candidate: Path, root: Path) -> Path:
    resolved = _resolve(candidate)
    root = _resolve(root)
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"Path must stay under {root}")
    return resolved


def browse_directory(settings: Settings, root_id: str | None = None, path: str = "") -> dict[str, Any]:
    root = _root_path(settings, root_id)
    target_dir = _ensure_inside(root / path, root)
    if not target_dir.is_dir():
        raise ValueError("Not a directory")

    folders: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for entry in target_dir.iterdir():
        try:
            relative_path = str(entry.relative_to(root)).replace("\\", "/")
            item = {
                "name": entry.name,
                "root_id": str(root_id or _root_id_for_path(settings, root)),
                "relative_path": relative_path,
                "select_path": str(entry),
            }
            if entry.is_dir():
                folders.append(item)
            elif entry.is_file():
                suffix = entry.suffix.lower()
                item.update(
                    {
                        "size_bytes": entry.stat().st_size,
                        "is_video": suffix in VIDEO_EXTENSIONS,
                    }
                )
                files.append(item)
        except OSError:
            continue

    folders.sort(key=lambda item: item["name"].lower())
    files.sort(key=lambda item: item["name"].lower())
    current_rel = str(target_dir.relative_to(root)).replace("\\", "/")
    if current_rel == ".":
        current_rel = ""
    parent_rel = None
    if current_rel:
        parent_rel = str(target_dir.parent.relative_to(root)).replace("\\", "/")
        if parent_rel == ".":
            parent_rel = ""
    root_info = next(root_info for root_info in browse_roots(settings) if Path(root_info["path"]) == root)
    return {
        "root_id": root_info["id"],
        "root_label": root_info["label"],
        "root_path": str(root),
        "current_path": current_rel,
        "current_select_path": str(target_dir),
        "parent_path": parent_rel,
        "roots": browse_roots(settings),
        "folders": folders,
        "files": files,
    }


def _root_id_for_path(settings: Settings, path: Path) -> str:
    resolved = _resolve(path)
    for root in browse_roots(settings):
        if Path(root["path"]) == resolved:
            return root["id"]
    return "0"


def resolve_managed_path(
    settings: Settings,
    path_value: str,
    default_subdir: str = "",
    must_exist: bool = False,
) -> Path:
    raw = Path(path_value)
    roots = [Path(root["path"]) for root in browse_roots(settings)]
    if raw.is_absolute():
        for root in roots:
            try:
                resolved = _ensure_inside(raw, root)
                if must_exist and not resolved.exists():
                    raise ValueError(f"Path does not exist: {resolved}")
                return resolved
            except ValueError:
                continue
        raise ValueError("Path is outside configured browse roots")

    parts = Path(path_value).parts
    if parts and parts[0] in DATA_SUBDIRS:
        candidate = settings.data_dir / path_value
    elif default_subdir:
        candidate = settings.data_dir / default_subdir / path_value
    else:
        candidate = settings.data_dir / path_value
    resolved = _ensure_inside(candidate, _resolve(settings.data_dir))
    if must_exist and not resolved.exists():
        raise ValueError(f"Path does not exist: {resolved}")
    return resolved
