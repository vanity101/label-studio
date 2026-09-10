"""把 high_cam RGB 物化为 preview.mp4。不改写 hdf5。"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

from . import RobotDependencyError, RobotImportError, preview_path, require_pillow
from . import yam_hdf5


class MaterializeError(RobotImportError):
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
        raise RobotDependencyError("未找到 ffprobe；请安装 ffmpeg") from exc
    out = proc.stdout.strip()
    if proc.returncode != 0 or not out or out in {"N/A", "unknown"}:
        return None
    try:
        return int(out)
    except ValueError:
        return None


def _write_jpegs(frames: Iterator[np.ndarray], frames_dir: Path) -> int:
    Image = require_pillow()
    count = 0
    for arr in frames:
        count += 1
        Image.fromarray(arr).save(frames_dir / f"{count:06d}.jpg", format="JPEG", quality=95)
    if count == 0:
        raise MaterializeError("rgb/data 没有帧")
    return count


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
        raise RobotDependencyError("未找到 ffmpeg；请安装系统包 ffmpeg") from exc
    if proc.returncode != 0 or not tmp.is_file():
        if tmp.exists():
            tmp.unlink()
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise MaterializeError(f"ffmpeg failed: {err}")
    os.replace(tmp, dest)


def materialize_episode(item: dict, preview_root: Path) -> dict:
    episode_id = item["episode_id"]
    cam_path = Path(item["camera_path"])
    fps = int(item["fps"])
    dest = preview_path(preview_root, episode_id)
    expected = yam_hdf5.frame_count(cam_path)
    if dest.is_file() and count_mp4_frames(dest) == expected:
        return {
            "episode_id": episode_id,
            "num_frames": expected,
            "fps": fps,
            "preview_path": str(dest),
            "skipped": True,
        }
    with tempfile.TemporaryDirectory(prefix="ls-hdf5-frames-") as tmp:
        frames_dir = Path(tmp)
        written = _write_jpegs(yam_hdf5.iter_rgb_frames(cam_path), frames_dir)
        _encode_mp4(frames_dir, dest, fps)
    probed = count_mp4_frames(dest)
    if probed != written:
        raise MaterializeError(f"preview frame count {probed} != rgb frames {written}")
    return {
        "episode_id": episode_id,
        "num_frames": written,
        "fps": fps,
        "preview_path": str(dest),
        "skipped": False,
    }
