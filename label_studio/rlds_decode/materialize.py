"""把一条 RLDS episode 物化为 preview.mp4。不改写 TFRecord。"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

import numpy as np

from . import RldsDecodeError, RldsDependencyError, preview_path, require_pillow, rlds_fps
from . import rlds as rlds_mod

PREVIEW_NAME = "preview.mp4"


class MaterializeError(RldsDecodeError):
    """物化失败（ffmpeg 缺失、编码失败、帧数对不上等）。"""


def count_mp4_frames(path: Path) -> Optional[int]:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-count_frames",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=nb_read_frames",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RldsDependencyError("未找到 ffprobe；请安装 ffmpeg") from exc
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out or out in {"N/A", "unknown"}:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def _extract_frames(episode: Any) -> list[np.ndarray]:
    frames: list[np.ndarray] = []
    for step in episode["steps"].as_numpy_iterator():
        obs = step["observation"]
        image = obs["image"] if isinstance(obs, dict) else obs
        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        elif arr.shape[-1] == 4:
            arr = arr[..., :3]
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        frames.append(arr)
    return frames


def _write_jpegs(frames: list[np.ndarray], frames_dir: Path) -> None:
    Image = require_pillow()
    for i, arr in enumerate(frames, start=1):
        Image.fromarray(arr).save(frames_dir / f"{i:06d}.jpg", format="JPEG", quality=95)


def _encode_mp4(frames_dir: Path, dest: Path, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".partial.mp4")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "%06d.jpg"),
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-fps_mode",
        "passthrough",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        str(tmp),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RldsDependencyError("未找到 ffmpeg；请安装系统包 ffmpeg") from exc
    if proc.returncode != 0 or not tmp.is_file():
        if tmp.exists():
            tmp.unlink()
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise MaterializeError(f"ffmpeg failed: {err}")
    os.replace(tmp, dest)


def materialize_loaded_episode(
    found: dict,
    preview_root: Path,
    *,
    fps: Optional[int] = None,
) -> dict:
    episode_id = found["episode_id"]
    frames = _extract_frames(found["episode"])
    num_frames = len(frames)
    dest = preview_path(preview_root, episode_id)
    skipped = False
    use_fps = fps if fps is not None else rlds_fps()

    if dest.is_file():
        existing = count_mp4_frames(dest)
        if existing == num_frames:
            skipped = True

    if not skipped:
        with tempfile.TemporaryDirectory(prefix="ls-rlds-frames-") as tmp:
            frames_dir = Path(tmp)
            _write_jpegs(frames, frames_dir)
            _encode_mp4(frames_dir, dest, use_fps)
        written = count_mp4_frames(dest)
        if written != num_frames:
            raise MaterializeError(f"preview frame count {written} != len(steps) {num_frames}")

    return {
        "episode_id": episode_id,
        "source_type": "rlds",
        "source": found["source"],
        "split": found["split"],
        "skipped": skipped,
        "num_frames": num_frames,
        "fps": use_fps,
        "fps_assumed": True,
        "preview_path": str(dest),
        "materialized": True,
    }


def materialize_episode(
    bronze: Path,
    episode_id: str,
    preview_root: Path,
    *,
    fps: Optional[int] = None,
) -> Optional[dict]:
    found = rlds_mod.locate_episode(bronze, episode_id)
    if found is None:
        return None
    found = {**found, "episode_id": episode_id}
    return materialize_loaded_episode(found, preview_root, fps=fps)
