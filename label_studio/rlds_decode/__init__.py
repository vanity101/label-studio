"""RLDS / TFRecord → preview.mp4（本进程库，不是旁路 FastAPI）。

移植自 vanity101/annotator-platform 的只读物化逻辑：
step 与帧 1:1，不抽帧，不改写 TFRecord。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_FPS = 10
DEFAULT_MAX_EPISODES = 16


class RldsDecodeError(RuntimeError):
    """用户可理解的解码/导入失败（缺元数据、混传、非法 zip 等）。"""


class RldsDependencyError(RldsDecodeError):
    """缺 tensorflow / tensorflow-datasets / ffmpeg / Pillow。"""


def rlds_fps() -> int:
    raw = os.environ.get("RLDS_FPS", str(DEFAULT_FPS)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RldsDecodeError(f"RLDS_FPS 必须是整数，实际 {raw!r}") from exc
    if value <= 0:
        raise RldsDecodeError(f"RLDS_FPS 必须 > 0，实际 {value}")
    return value


def rlds_max_episodes() -> int:
    raw = os.environ.get("RLDS_IMPORT_MAX_EPISODES", str(DEFAULT_MAX_EPISODES)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RldsDecodeError(f"RLDS_IMPORT_MAX_EPISODES 必须是整数，实际 {raw!r}") from exc
    if value <= 0:
        raise RldsDecodeError(f"RLDS_IMPORT_MAX_EPISODES 必须 > 0，实际 {value}")
    return value


def _disable_tf_cloud_lookups() -> None:
    """本地 TFRecord 解码不访问 GCE / GCS；国内网络连 Google 会把导入卡住。"""
    os.environ.setdefault("NO_GCE_CHECK", "true")
    os.environ.setdefault("GCE_METADATA_TIMEOUT", "0")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def require_tfds():
    _disable_tf_cloud_lookups()
    try:
        import tensorflow_datasets as tfds
    except ImportError as exc:
        raise RldsDependencyError(
            "RLDS 解码需要 tensorflow 与 tensorflow-datasets。"
            "请安装: pip install 'label-studio[rlds]' -i https://pypi.tuna.tsinghua.edu.cn/simple"
        ) from exc
    try:
        from tensorflow_datasets.core.utils import gcs_utils

        gcs_utils._is_gcs_disabled = True  # noqa: SLF001
    except Exception:
        pass
    return tfds


def require_pillow():
    try:
        from PIL import Image
    except ImportError as exc:
        raise RldsDependencyError(
            "RLDS 解码需要 Pillow。请安装: pip install 'label-studio[rlds]' "
            "-i https://pypi.tuna.tsinghua.edu.cn/simple"
        ) from exc
    return Image


def preview_path(preview_root: Path, episode_id: str) -> Path:
    return Path(preview_root) / episode_id / "preview.mp4"
