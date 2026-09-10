"""只读打开 YAM schema v3 的 high_cam RGB。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import numpy as np

from . import DEFAULT_CAMERA, RobotImportError, require_h5py
from .detect import high_cam_path


def episode_id_for(episode_dir: Path) -> str:
    name = episode_dir.name
    if name.startswith("episode_"):
        return name
    return f"episode_{name}"


def read_fps(cam_path: Path) -> int:
    h5py = require_h5py()
    with h5py.File(cam_path, "r") as handle:
        rgb = handle.get("rgb")
        if rgb is not None and "requested_hz" in rgb.attrs:
            raw = rgb.attrs["requested_hz"]
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise RobotImportError(f"{cam_path.name} rgb.requested_hz 无法解析: {raw!r}") from exc
            if value > 0:
                return value
    return 30


def iter_rgb_frames(cam_path: Path) -> Iterator[np.ndarray]:
    h5py = require_h5py()
    with h5py.File(cam_path, "r") as handle:
        if "rgb/data" not in handle:
            raise RobotImportError(f"{cam_path.name} 没有 rgb/data")
        dataset = handle["rgb/data"]
        if dataset.ndim != 4 or dataset.shape[-1] not in {3, 4}:
            raise RobotImportError(
                f"{cam_path.name} rgb/data 形状应为 [T,H,W,3]，实际 {dataset.shape}"
            )
        for index in range(int(dataset.shape[0])):
            arr = np.asarray(dataset[index])
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            elif arr.shape[-1] == 4:
                arr = arr[..., :3]
            if arr.dtype != np.uint8:
                arr = np.clip(arr, 0, 255).astype(np.uint8)
            yield arr


def frame_count(cam_path: Path) -> int:
    h5py = require_h5py()
    with h5py.File(cam_path, "r") as handle:
        if "rgb/data" not in handle:
            raise RobotImportError(f"{cam_path.name} 没有 rgb/data")
        return int(handle["rgb/data"].shape[0])


def list_episodes(bronze: Path) -> list[dict]:
    from .detect import require_yam_episodes

    items: list[dict] = []
    for directory in require_yam_episodes(bronze):
        cam = high_cam_path(directory)
        if cam is None:
            continue
        items.append(
            {
                "episode_id": episode_id_for(directory),
                "episode_dir": directory,
                "camera_path": cam,
                "camera": DEFAULT_CAMERA,
                "fps": read_fps(cam),
            }
        )
    return items
