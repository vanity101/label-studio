"""YAM / LeRobot 目录 → LS 任务 dict（无 Django 依赖）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import DEFAULT_CAMERA, import_max_episodes
from . import yam_hdf5
from .lerobot_detect import resolve_lerobot_dataset_root
from .lerobot_format import list_episodes as list_lerobot_episodes
from .lerobot_materialize import materialize_episode as materialize_lerobot_episode
from .materialize import materialize_episode


@dataclass
class DecodeResult:
    tasks: list[dict] = field(default_factory=list)
    skipped_episode_ids: list[str] = field(default_factory=list)
    truncated: bool = False
    listed: int = 0


def skip_existing(episode_ids: list[str], existing: set[str]) -> tuple[list[str], list[str]]:
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
) -> DecodeResult:
    existing = existing_episode_ids or set()
    limit = max_episodes if max_episodes is not None else import_max_episodes()
    result = DecodeResult()
    for item in yam_hdf5.list_episodes(bronze):
        result.listed += 1
        episode_id = item["episode_id"]
        if episode_id in existing:
            result.skipped_episode_ids.append(episode_id)
            continue
        if len(result.tasks) >= limit:
            result.truncated = True
            break
        materialized = materialize_episode(item, preview_root)
        preview = materialized["preview_path"]
        result.tasks.append(
            {
                "data": {
                    "video": preview if preview.endswith(".mp4") else f"{preview}.mp4",
                    "episode_id": episode_id,
                    "source_type": "yam_hdf5",
                    "camera": item.get("camera") or DEFAULT_CAMERA,
                    "num_frames": materialized["num_frames"],
                    "fps": materialized["fps"],
                    "fps_assumed": False,
                }
            }
        )
    return result


def decode_lerobot_to_tasks(
    bronze: Path,
    preview_root: Path,
    *,
    existing_episode_ids: Optional[set[str]] = None,
    max_episodes: Optional[int] = None,
) -> DecodeResult:
    existing = existing_episode_ids or set()
    limit = max_episodes if max_episodes is not None else import_max_episodes()
    result = DecodeResult()
    dataset_root = resolve_lerobot_dataset_root(bronze)
    for item in list_lerobot_episodes(dataset_root):
        result.listed += 1
        episode_id = item["episode_id"]
        if episode_id in existing:
            result.skipped_episode_ids.append(episode_id)
            continue
        if len(result.tasks) >= limit:
            result.truncated = True
            break
        materialized = materialize_lerobot_episode(item, preview_root, dataset_root=dataset_root)
        preview = str(materialized["preview_path"])
        camera = materialized.get("camera") or item.get("camera") or DEFAULT_CAMERA
        fps = materialized.get("fps")
        if fps is None:
            fps = item.get("fps")
        result.tasks.append(
            {
                "data": {
                    "video": preview if preview.endswith(".mp4") else f"{preview}.mp4",
                    "episode_id": episode_id,
                    "source_type": "lerobot",
                    "camera": camera,
                    "num_frames": materialized["num_frames"],
                    "fps": fps,
                    "fps_assumed": False,
                }
            }
        )
    return result


def _decode_to_tasks_isolated(
    bronze: Path,
    preview_root: Path,
    *,
    existing_episode_ids: Optional[set[str]] = None,
    max_episodes: Optional[int] = None,
    source: str = "yam_hdf5",
) -> DecodeResult:
    import json
    import os
    import subprocess
    import sys
    import tempfile

    from . import RobotImportError

    label = "LeRobot" if source == "lerobot" else "HDF5"
    prefix = "ls-lerobot-out-" if source == "lerobot" else "ls-hdf5-out-"
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    ls_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = ls_root if not pythonpath else f"{ls_root}{os.pathsep}{pythonpath}"

    with tempfile.NamedTemporaryFile(prefix=prefix, suffix=".json", delete=False) as handle:
        out_path = Path(handle.name)
    python = (
        os.environ.get("ROBOT_IMPORT_PYTHON", "").strip()
        or os.environ.get("RLDS_PYTHON", "").strip()
        or sys.executable
    )
    cmd = [
        python,
        "-m",
        "robot_import.worker",
        str(bronze),
        str(preview_root),
        "--out",
        str(out_path),
    ]
    if source == "lerobot":
        cmd.extend(["--source", "lerobot"])
    if existing_episode_ids:
        cmd.extend(["--existing", ",".join(sorted(existing_episode_ids))])
    if max_episodes is not None:
        cmd.extend(["--max-episodes", str(max_episodes)])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600, check=False)
    except subprocess.TimeoutExpired as cop:
        raise RobotImportError(f"{label} 解码超时") from cop
    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RobotImportError(f"{label} 解码失败: {err}")
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    out_path.unlink(missing_ok=True)
    if not payload.get("ok"):
        raise RobotImportError(payload.get("error") or f"{label} 解码失败")
    return DecodeResult(
        tasks=payload["tasks"],
        skipped_episode_ids=payload["skipped_episode_ids"],
        truncated=payload["truncated"],
        listed=payload["listed"],
    )


def decode_bronze_to_tasks_isolated(
    bronze: Path,
    preview_root: Path,
    *,
    existing_episode_ids: Optional[set[str]] = None,
    max_episodes: Optional[int] = None,
) -> DecodeResult:
    return _decode_to_tasks_isolated(
        bronze,
        preview_root,
        existing_episode_ids=existing_episode_ids,
        max_episodes=max_episodes,
        source="yam_hdf5",
    )


def decode_lerobot_to_tasks_isolated(
    bronze: Path,
    preview_root: Path,
    *,
    existing_episode_ids: Optional[set[str]] = None,
    max_episodes: Optional[int] = None,
) -> DecodeResult:
    return _decode_to_tasks_isolated(
        bronze,
        preview_root,
        existing_episode_ids=existing_episode_ids,
        max_episodes=max_episodes,
        source="lerobot",
    )
