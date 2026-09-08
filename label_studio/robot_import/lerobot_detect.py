"""暂存根内容判别：yam_hdf5 | lerobot | mixed | empty。不改 detect.py。"""

from __future__ import annotations

import json
from pathlib import Path

from .detect import find_episode_dirs

ClassifyKind = str


def classify_staged_root(path: Path | str) -> ClassifyKind:
    """Content gate：YAM episode 与 LeRobot v2 根互斥；都不是则为 empty。"""
    root = Path(path)
    if not root.is_dir():
        return "empty"
    yam = bool(_yam_episode_dirs(root))
    lerobot = bool(_lerobot_dataset_roots(root))
    if yam and lerobot:
        return "mixed"
    if yam:
        return "yam_hdf5"
    if lerobot:
        return "lerobot"
    return "empty"


def _under_images(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        relative = path
    return "images" in relative.parts


def _yam_episode_dirs(root: Path) -> list[Path]:
    found: list[Path] = []
    for directory in find_episode_dirs(root):
        if _under_images(directory, root):
            continue
        found.append(directory)
    return found


def _lerobot_dataset_roots(root: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for info_json in sorted(root.rglob("info.json")):
        if _under_images(info_json, root):
            continue
        if info_json.parent.name != "meta":
            continue
        dataset_root = info_json.parent.parent
        resolved = dataset_root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if _is_lerobot_v2_root(dataset_root, root):
            found.append(dataset_root)
    return found


def _is_lerobot_v2_root(dataset_root: Path, staged_root: Path) -> bool:
    info_path = dataset_root / "meta" / "info.json"
    if not info_path.is_file():
        return False
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(info, dict):
        return False
    version = str(info.get("codebase_version") or "").strip()
    if not version.startswith("v2"):
        return False
    return _can_list_episodes(dataset_root, staged_root, info)


def _can_list_episodes(dataset_root: Path, staged_root: Path, info: dict) -> bool:
    data_dir = dataset_root / "data"
    if data_dir.is_dir():
        for parquet in data_dir.rglob("*.parquet"):
            if _under_images(parquet, staged_root):
                continue
            if parquet.is_file():
                return True
    jsonl = dataset_root / "meta" / "episodes.jsonl"
    if jsonl.is_file() and not _under_images(jsonl, staged_root):
        try:
            text = jsonl.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        if any(line.strip() for line in text.splitlines()):
            return True
    try:
        return int(info.get("total_episodes") or 0) >= 1
    except (TypeError, ValueError):
        return False
