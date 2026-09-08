"""只读解析 HuggingFace LeRobot v2 / v2.1 数据集布局。不改源文件。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import RobotImportError

DEFAULT_CHUNKS_SIZE = 1000
DEFAULT_VIDEO_PATH = (
    "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4"
)


def _as_root(root: Path | str) -> Path:
    path = Path(root)
    if not path.is_dir():
        raise RobotImportError(f"LeRobot 根路径不是目录: {path}")
    return path


def info_json_path(root: Path | str) -> Path:
    return _as_root(root) / "meta" / "info.json"


def parse_info(root: Path | str) -> dict[str, Any]:
    """读取 `meta/info.json`，拒绝非 v2 与缺元数据。"""
    dataset_root = _as_root(root)
    path = info_json_path(dataset_root)
    if not path.is_file():
        raise RobotImportError("缺少 meta/info.json，无法识别为 LeRobot 数据集")
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RobotImportError(f"meta/info.json 不是合法 JSON: {exc}") from exc
    if not isinstance(info, dict):
        raise RobotImportError("meta/info.json 必须是 JSON 对象")

    version = str(info.get("codebase_version") or "").strip()
    if not version.startswith("v2"):
        raise RobotImportError(
            f"仅支持 LeRobot v2 / v2.1，实际 codebase_version={version or '(空)'}"
        )

    video_feature = pick_video_feature(info)
    fps = fps_from_info(info, video_feature)
    return {
        "root": dataset_root,
        "info": info,
        "codebase_version": version,
        "video_feature": video_feature,
        "fps": fps,
    }


def video_feature_keys(info: dict[str, Any]) -> list[str]:
    features = info.get("features")
    if not isinstance(features, dict) or not features:
        raise RobotImportError("meta/info.json 缺少 features，无法选择预览视频")
    keys = [
        name
        for name, spec in features.items()
        if isinstance(spec, dict) and str(spec.get("dtype") or "").lower() == "video"
    ]
    if not keys:
        raise RobotImportError("meta/info.json 没有 dtype=video 的特征，无法预览")
    return keys


def _video_rank(name: str) -> int:
    lower = name.lower()
    if "cam_high" in lower or "high" in lower or "head" in lower:
        return 0
    if "laptop" in lower:
        return 1
    return 2


def pick_video_feature(info: dict[str, Any]) -> str:
    """ASM-002：high/head/cam_high → laptop → 第一个 video 特征。"""
    keys = video_feature_keys(info)
    return min(keys, key=lambda name: (_video_rank(name), keys.index(name)))


def fps_from_info(info: dict[str, Any], video_feature: str | None = None) -> float:
    raw = info.get("fps")
    fps = _positive_fps(raw)
    if fps is not None:
        return fps
    feature_name = video_feature or pick_video_feature(info)
    spec = (info.get("features") or {}).get(feature_name) or {}
    extra = spec.get("info") if isinstance(spec, dict) else None
    if isinstance(extra, dict):
        for key in ("video.fps", "fps"):
            fps = _positive_fps(extra.get(key))
            if fps is not None:
                return fps
    raise RobotImportError("meta/info.json 缺少可用 fps，无法导入")


def _positive_fps(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def list_episodes(root: Path | str) -> list[dict[str, Any]]:
    parsed = parse_info(root)
    dataset_root: Path = parsed["root"]
    info: dict[str, Any] = parsed["info"]
    video_feature: str = parsed["video_feature"]
    fps: float = parsed["fps"]
    camera = video_feature.rsplit(".", 1)[-1]

    items: list[dict[str, Any]] = []
    for index, episode_id in _episode_ids(dataset_root, info):
        video_path = resolve_video_path(dataset_root, info, video_feature, index)
        if video_path is None or not video_path.is_file():
            continue
        items.append(
            {
                "episode_id": episode_id,
                "index": index,
                "video_path": video_path,
                "fps": fps,
                "camera": camera,
            }
        )
    if not items:
        raise RobotImportError("没有可预览的集：缺少对应 mp4，或视频特征无法落到文件")
    return items


def _episode_ids(root: Path, info: dict[str, Any]) -> list[tuple[int, str]]:
    jsonl = root / "meta" / "episodes.jsonl"
    if jsonl.is_file():
        rows: list[tuple[int, str]] = []
        for line_no, raw in enumerate(jsonl.read_text(encoding="utf-8").splitlines(), start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RobotImportError(f"meta/episodes.jsonl 第 {line_no} 行不是合法 JSON") from exc
            if not isinstance(row, dict):
                raise RobotImportError(f"meta/episodes.jsonl 第 {line_no} 行必须是对象")
            index = _episode_index(row, line_no)
            episode_id = str(row.get("episode_id") or "").strip() or f"episode_{index:06d}"
            rows.append((index, episode_id))
        if rows:
            return rows

    total = info.get("total_episodes")
    try:
        count = int(total)
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        raise RobotImportError("无法列出 episode：缺少 meta/episodes.jsonl 且 total_episodes 无效")
    return [(index, f"episode_{index:06d}") for index in range(count)]


def _episode_index(row: dict[str, Any], line_no: int) -> int:
    raw = row.get("episode_index", row.get("index"))
    try:
        index = int(raw)
    except (TypeError, ValueError) as exc:
        raise RobotImportError(f"meta/episodes.jsonl 第 {line_no} 行缺少 episode_index") from exc
    if index < 0:
        raise RobotImportError(f"meta/episodes.jsonl 第 {line_no} 行 episode_index 必须 ≥ 0")
    return index


def resolve_video_path(
    root: Path,
    info: dict[str, Any],
    video_feature: str,
    episode_index: int,
) -> Path | None:
    chunks_size = info.get("chunks_size") or DEFAULT_CHUNKS_SIZE
    try:
        chunk = int(episode_index) // int(chunks_size)
    except (TypeError, ValueError, ZeroDivisionError):
        chunk = episode_index // DEFAULT_CHUNKS_SIZE

    template = str(info.get("video_path") or DEFAULT_VIDEO_PATH)
    candidates: list[Path] = []
    try:
        relative = template.format(
            episode_chunk=chunk,
            video_key=video_feature,
            episode_index=episode_index,
        )
        candidates.append(root / relative)
    except (KeyError, ValueError):
        pass
    candidates.extend(
        [
            root / "videos" / "chunk-{0:03d}".format(chunk) / video_feature / f"episode_{episode_index:06d}.mp4",
            root / "videos" / video_feature / f"episode_{episode_index:06d}.mp4",
        ]
    )
    seen: set[Path] = set()
    for path in candidates:
        resolved = path if path.is_absolute() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved.resolve()
    return None
