"""机器人数据集导入：HDF5（本轮）与后续 LeRobot 共用管道。不是旁路 FastAPI。"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_MAX_EPISODES = 16
DEFAULT_CAMERA = "high_cam"


class RobotImportError(RuntimeError):
    """用户可理解的导入失败（缺元数据、混传、非法 zip 等）。"""


class RobotDependencyError(RobotImportError):
    """缺 h5py / ffmpeg / Pillow。"""


def import_max_episodes() -> int:
    raw = os.environ.get("ROBOT_IMPORT_MAX_EPISODES", str(DEFAULT_MAX_EPISODES)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RobotImportError(f"ROBOT_IMPORT_MAX_EPISODES 必须是整数，实际 {raw!r}") from exc
    if value <= 0:
        raise RobotImportError(f"ROBOT_IMPORT_MAX_EPISODES 必须 > 0，实际 {value}")
    return value


def require_h5py():
    try:
        import h5py
    except ImportError as exc:
        raise RobotDependencyError(
            "HDF5 导入需要 h5py。"
            "请安装: pip install h5py -i https://pypi.tuna.tsinghua.edu.cn/simple "
            "--trusted-host pypi.tuna.tsinghua.edu.cn"
        ) from exc
    return h5py


def require_pillow():
    try:
        from PIL import Image
    except ImportError as exc:
        raise RobotDependencyError(
            "HDF5 导入需要 Pillow。"
            "请安装: pip install Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple "
            "--trusted-host pypi.tuna.tsinghua.edu.cn"
        ) from exc
    return Image


def preview_path(preview_root: Path, episode_id: str) -> Path:
    return Path(preview_root) / episode_id / "preview.mp4"
