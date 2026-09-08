"""把 LeRobot 集物化为 preview.mp4。不改源文件，不读 images/。"""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator

from . import RobotDependencyError, RobotImportError, preview_path, require_pillow
from .lerobot_format import DEFAULT_CHUNKS_SIZE, parse_info

HIGH_CAM_COLUMN = "observation.images.high_cam"
DEFAULT_DATA_PATH = "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet"
DEFAULT_FPS = 30


class MaterializeError(RobotImportError):
    """物化失败（缺预览源、ffmpeg、列缺失等）。"""


def require_pyarrow():
    try:
        import pyarrow
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RobotDependencyError(
            "LeRobot parquet 预览需要 pyarrow。"
            "请安装: pip install pyarrow -i https://pypi.tuna.tsinghua.edu.cn/simple "
            "--trusted-host pypi.tuna.tsinghua.edu.cn"
        ) from exc
    return pyarrow, pq


def count_mp4_frames(path: Path) -> int | None:
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


def _as_video_file(raw: Any) -> Path | None:
    if raw in (None, "", "null"):
        return None
    path = Path(raw)
    if path.is_file():
        return path.resolve()
    return None


def _chunk_index(info: dict[str, Any], episode_index: int) -> int:
    chunks_size = info.get("chunks_size") or DEFAULT_CHUNKS_SIZE
    try:
        return int(episode_index) // int(chunks_size)
    except (TypeError, ValueError, ZeroDivisionError):
        return episode_index // DEFAULT_CHUNKS_SIZE


def resolve_parquet_path(
    root: Path,
    info: dict[str, Any],
    episode_index: int,
) -> Path | None:
    chunk = _chunk_index(info, episode_index)
    raw_template = info.get("data_path")
    template = DEFAULT_DATA_PATH if raw_template in (None, "", "null") else str(raw_template)
    candidates: list[Path] = []
    try:
        candidates.append(
            root
            / template.format(
                episode_chunk=chunk,
                episode_index=episode_index,
            )
        )
    except (KeyError, ValueError):
        pass
    candidates.extend(
        [
            root / "data" / f"chunk-{chunk:03d}" / f"episode_{episode_index:06d}.parquet",
            root / "data" / f"episode_{episode_index:06d}.parquet",
        ]
    )
    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path.resolve()
    return None


def _frame_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        return data or None
    if isinstance(value, dict):
        raw = value.get("bytes")
        if raw is None:
            return None
        return _frame_bytes(raw)
    return None


def iter_high_cam_frame_bytes(parquet_path: Path) -> Iterator[bytes]:
    """只读 observation.images.high_cam，禁止整表 / 其它相机列。"""
    _pa, pq = require_pyarrow()
    try:
        parquet_file = pq.ParquetFile(str(parquet_path))
    except Exception as exc:  # noqa: BLE001
        raise MaterializeError(f"无法打开 parquet: {parquet_path.name}: {exc}") from exc

    names = list(parquet_file.schema_arrow.names)
    if HIGH_CAM_COLUMN not in names:
        raise MaterializeError(
            f"parquet 没有 {HIGH_CAM_COLUMN}，无法派生预览（不得改用其它相机列）"
        )

    found = 0
    try:
        batches = parquet_file.iter_batches(columns=[HIGH_CAM_COLUMN])
    except Exception as exc:  # noqa: BLE001
        raise MaterializeError(f"读取 {HIGH_CAM_COLUMN} 失败: {exc}") from exc

    for batch in batches:
        column = batch.column(0)
        for index in range(batch.num_rows):
            payload = _frame_bytes(column[index].as_py())
            if not payload:
                continue
            found += 1
            yield payload
    if found == 0:
        raise MaterializeError(f"{HIGH_CAM_COLUMN} 没有可用帧")


def _write_jpegs_from_bytes(frames: Iterator[bytes], frames_dir: Path) -> int:
    Image = require_pillow()
    count = 0
    for payload in frames:
        count += 1
        try:
            image = Image.open(io.BytesIO(payload))
            image = image.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise MaterializeError(f"high_cam 第 {count} 帧不是可解码图像: {exc}") from exc
        image.save(frames_dir / f"{count:06d}.jpg", format="JPEG", quality=95)
    if count == 0:
        raise MaterializeError(f"{HIGH_CAM_COLUMN} 没有可用帧")
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


def _int_fps(raw: Any) -> int:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_FPS
    if value <= 0:
        return DEFAULT_FPS
    return max(1, int(round(value)))


def _dataset_root(item: dict, dataset_root: Path | str | None) -> Path | None:
    if dataset_root not in (None, ""):
        path = Path(dataset_root)
        return path if path.is_dir() else None
    raw = item.get("root") or item.get("dataset_root")
    if raw not in (None, ""):
        path = Path(raw)
        return path if path.is_dir() else None
    return None


def _copy_preview(source: Path, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    skipped = dest.is_file() and dest.stat().st_size == source.stat().st_size
    if not skipped:
        shutil.copyfile(source, dest)
    frames = count_mp4_frames(dest)
    return {
        "num_frames": frames,
        "preview_path": str(dest),
        "skipped": skipped,
        "copied": True,
    }


def _encode_from_parquet(parquet_path: Path, dest: Path, fps: int) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ls-lerobot-frames-") as tmp:
        frames_dir = Path(tmp)
        written = _write_jpegs_from_bytes(iter_high_cam_frame_bytes(parquet_path), frames_dir)
        if dest.is_file() and count_mp4_frames(dest) == written:
            return {
                "num_frames": written,
                "preview_path": str(dest),
                "skipped": True,
                "copied": False,
            }
        _encode_mp4(frames_dir, dest, fps)
    probed = count_mp4_frames(dest)
    if probed != written:
        raise MaterializeError(f"preview frame count {probed} != high_cam frames {written}")
    return {
        "num_frames": written,
        "preview_path": str(dest),
        "skipped": False,
        "copied": False,
    }


def _missing_preview_error() -> MaterializeError:
    return MaterializeError(
        "没有可用 mp4（videos/ 或 video_path），也没有 observation.images.high_cam，无法生成预览"
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_episode(
    item: dict,
    preview_root: Path,
    *,
    dataset_root: Path | str | None = None,
) -> dict:
    """有可用 mp4 则复制为 preview.mp4（不重编）；否则从 parquet high_cam 派生。"""
    episode_id = str(item["episode_id"])
    dest = preview_path(preview_root, episode_id)
    fps = _int_fps(item.get("fps"))
    source_mp4 = _as_video_file(item.get("video_path"))
    root = _dataset_root(item, dataset_root)

    if source_mp4 is not None:
        result = _copy_preview(source_mp4, dest)
        return {
            "episode_id": episode_id,
            "fps": fps,
            "camera": item.get("camera") or "high_cam",
            **result,
        }

    if root is None:
        raise _missing_preview_error()

    parsed = parse_info(root)
    info = parsed["info"]
    if not fps or fps == DEFAULT_FPS:
        info_fps = parsed.get("fps")
        if info_fps:
            fps = _int_fps(info_fps)

    episode_index = item.get("index")
    if episode_index is None:
        episode_index = 0
    try:
        episode_index = int(episode_index)
    except (TypeError, ValueError) as exc:
        raise MaterializeError(f"episode index 无效: {episode_index!r}") from exc

    parquet_path = resolve_parquet_path(root, info, episode_index)
    if parquet_path is None:
        raise _missing_preview_error()

    result = _encode_from_parquet(parquet_path, dest, fps)
    return {
        "episode_id": episode_id,
        "fps": fps,
        "camera": item.get("camera") or "high_cam",
        **result,
    }
