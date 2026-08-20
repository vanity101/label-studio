"""把 Bronze 目录物化成 LS 任务 dict（无 Django 依赖）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import rlds_fps, rlds_max_episodes
from .rlds import walk_episodes


@dataclass
class DecodeResult:
    tasks: list[dict] = field(default_factory=list)
    skipped_episode_ids: list[str] = field(default_factory=list)
    truncated: bool = False
    listed: int = 0


def skip_existing(episode_ids: list[str], existing: set[str]) -> tuple[list[str], list[str]]:
    """返回 (待导入, 已存在而跳过)。"""
    pending: list[str] = []
    skipped: list[str] = []
    for episode_id in episode_ids:
        if episode_id in existing:
            skipped.append(episode_id)
        else:
            pending.append(episode_id)
    return pending, skipped


def decode_bronze_to_tasks(
    bronze: Path,
    preview_root: Path,
    *,
    existing_episode_ids: Optional[set[str]] = None,
    max_episodes: Optional[int] = None,
    fps: Optional[int] = None,
) -> DecodeResult:
    from .materialize import materialize_loaded_episode

    existing = existing_episode_ids or set()
    limit = max_episodes if max_episodes is not None else rlds_max_episodes()
    use_fps = fps if fps is not None else rlds_fps()
    result = DecodeResult()

    for item in walk_episodes(bronze):
        result.listed += 1
        episode_id = item["episode_id"]
        if episode_id in existing:
            result.skipped_episode_ids.append(episode_id)
            continue
        if len(result.tasks) >= limit:
            result.truncated = True
            break
        materialized = materialize_loaded_episode(item, preview_root, fps=use_fps)
        preview = materialized["preview_path"]
        result.tasks.append(
            {
                "data": {
                    "video": preview if preview.endswith(".mp4") else f"{preview}.mp4",
                    "episode_id": episode_id,
                    "source_type": "rlds",
                    "num_frames": materialized["num_frames"],
                    "fps": materialized["fps"],
                    "fps_assumed": True,
                    "split": item.get("split"),
                }
            }
        )
    return result


def decode_bronze_to_tasks_isolated(
    bronze: Path,
    preview_root: Path,
    *,
    existing_episode_ids: Optional[set[str]] = None,
    max_episodes: Optional[int] = None,
    fps: Optional[int] = None,
) -> DecodeResult:
    """在独立进程里解码，避免 TensorFlow 在 Django 请求线程里死锁。"""
    import json
    import os
    import subprocess
    import sys
    import tempfile

    from . import RldsDecodeError

    env = os.environ.copy()
    env.setdefault("NO_GCE_CHECK", "true")
    env.setdefault("GCE_METADATA_TIMEOUT", "0")
    env.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    pythonpath = env.get("PYTHONPATH", "")
    ls_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = ls_root if not pythonpath else f"{ls_root}{os.pathsep}{pythonpath}"

    with tempfile.NamedTemporaryFile(prefix="ls-rlds-out-", suffix=".json", delete=False) as handle:
        out_path = Path(handle.name)
    python = os.environ.get("RLDS_PYTHON", "").strip() or sys.executable
    cmd = [
        python,
        "-m",
        "rlds_decode.worker",
        str(bronze),
        str(preview_root),
        "--out",
        str(out_path),
    ]
    if existing_episode_ids:
        cmd.extend(["--existing", ",".join(sorted(existing_episode_ids))])
    if max_episodes is not None:
        cmd.extend(["--max-episodes", str(max_episodes)])
    if fps is not None:
        cmd.extend(["--fps", str(fps)])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RldsDecodeError("RLDS 解码超时") from exc
    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RldsDecodeError(f"RLDS 解码失败: {err}")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    out_path.unlink(missing_ok=True)
    if not payload.get("ok"):
        raise RldsDecodeError(payload.get("error") or "RLDS 解码失败")
    return DecodeResult(
        tasks=payload["tasks"],
        skipped_episode_ids=payload["skipped_episode_ids"],
        truncated=payload["truncated"],
        listed=payload["listed"],
    )
