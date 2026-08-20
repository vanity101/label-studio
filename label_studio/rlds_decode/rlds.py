"""RLDS 只读列举与定位。不写回 TFRecord。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Optional

from . import DEFAULT_FPS, RldsDecodeError, RldsDependencyError, require_tfds
from .detect import has_tfrecord

RLDS_DEFAULT_FPS = DEFAULT_FPS


def _decode(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        value = value.numpy()
    except AttributeError:
        pass
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "episode"


def episode_id_for(source: str, split: str, index: int, meta: Any) -> str:
    file_path = _decode(meta.get("file_path")) if isinstance(meta, dict) else None
    if file_path:
        stem = Path(file_path).stem or file_path
        short = hashlib.sha1(file_path.encode("utf-8")).hexdigest()[:8]
        return f"{_slug(stem)}-{short}"
    return f"{source}-{split}-{index:05d}"


def _open_builder(bronze: Path):
    tfds = require_tfds()
    return tfds.builder_from_directory(str(bronze))


def _as_dataset(builder, split: str):
    """单线程读 TFRecord，避免 tf.data prefetch 在 Django 进程里和 GIL 死锁。"""
    tfds = require_tfds()
    read_config = tfds.ReadConfig(
        try_autocache=False,
        skip_prefetch=True,
        num_parallel_calls_for_decode=1,
        num_parallel_calls_for_interleave_files=1,
        interleave_cycle_length=1,
    )
    return builder.as_dataset(split=split, shuffle_files=False, read_config=read_config)


def count_steps(episode: Any) -> int:
    import numpy as np

    steps = episode["steps"]
    return int(steps.reduce(np.int64(0), lambda acc, _step: acc + 1).numpy())


def walk_episodes(bronze: Path, split: Optional[str] = None):
    """按 split 顺序只读遍历 episode，不预先扫完全部、不访问网络。"""
    if not has_tfrecord(bronze):
        return
    try:
        builder = _open_builder(bronze)
    except RldsDependencyError:
        raise
    except Exception as exc:
        raise RldsDecodeError(f"无法打开 RLDS 目录: {exc}") from exc

    source = builder.name
    available = list(builder.info.splits.keys())
    wanted = [split] if split else available
    for sp in wanted:
        if sp not in available:
            continue
        try:
            dataset = _as_dataset(builder, sp)
        except Exception:
            continue
        for index, episode in enumerate(dataset):
            meta = episode.get("episode_metadata", {})
            yield {
                "episode_id": episode_id_for(source, sp, index, meta),
                "source_type": "rlds",
                "source": source,
                "split": sp,
                "index": index,
                "episode": episode,
            }


def list_episodes(bronze: Path, split: Optional[str] = None) -> list[dict]:
    episodes: list[dict] = []
    for item in walk_episodes(bronze, split=split):
        episodes.append(
            {
                "episode_id": item["episode_id"],
                "source_type": item["source_type"],
                "source": item["source"],
                "split": item["split"],
                "index": item["index"],
                "num_frames": count_steps(item["episode"]),
            }
        )
    return episodes


def locate_episode(bronze: Path, episode_id: str) -> Optional[dict]:
    if not has_tfrecord(bronze):
        return None
    try:
        builder = _open_builder(bronze)
    except RldsDependencyError:
        raise
    except Exception as exc:
        raise RldsDecodeError(f"无法打开 RLDS 目录: {exc}") from exc
    source = builder.name
    for sp in builder.info.splits.keys():
        try:
            dataset = _as_dataset(builder, sp)
        except Exception:
            continue
        for index, episode in enumerate(dataset):
            meta = episode.get("episode_metadata", {})
            current_id = episode_id_for(source, sp, index, meta)
            if current_id == episode_id:
                return {"source": source, "split": sp, "episode": episode, "index": index}
    return None
