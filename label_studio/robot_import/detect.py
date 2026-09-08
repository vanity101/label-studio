"""识别 YAM HDF5 上传批次。不依赖 h5py / Django。"""

from __future__ import annotations

from pathlib import Path

from . import RobotImportError

YAM_META_NAMES = frozenset({"info.yaml", "info.yml", "manifest.yaml", "manifest.yml", "complete"})


def _as_path(name: str) -> Path:
    return Path(str(name).replace("\\", "/"))


def basename(name: str) -> str:
    return _as_path(name).name


def is_hdf5_name(name: str) -> bool:
    lower = basename(name).lower()
    return lower.endswith(".hdf5") or lower.endswith(".h5")


def is_zip_name(name: str) -> bool:
    return basename(name).lower().endswith(".zip")


def is_yaml_name(name: str) -> bool:
    lower = basename(name).lower()
    return lower.endswith(".yaml") or lower.endswith(".yml")


def is_yam_meta_name(name: str) -> bool:
    return basename(name).lower() in YAM_META_NAMES


def is_generated_preview_name(name: str) -> bool:
    return basename(name).lower().endswith("-preview.mp4")


def is_robot_filename(name: str) -> bool:
    return is_hdf5_name(name) or is_zip_name(name) or is_yam_meta_name(name)


def is_supported_upload_name(name: str, extra_extensions: set[str]) -> bool:
    if is_robot_filename(name):
        return True
    ext = _as_path(name).suffix.lower()
    return ext in extra_extensions


def strip_upload_uuid_prefix(stored_name: str) -> str:
    name = basename(stored_name)
    if len(name) > 9 and name[8] == "-" and all(ch in "0123456789abcdef" for ch in name[:8]):
        return name[9:]
    return name


def original_relative_name(stored_name: str) -> str:
    """保留相对目录，只去掉最后一段上的 8 位 uuid 前缀。"""
    path = _as_path(stored_name)
    parts = list(path.parts)
    if not parts:
        return stored_name
    parts[-1] = strip_upload_uuid_prefix(parts[-1])
    return str(Path(*parts)).replace("\\", "/")


def classify_upload_names(names: list[str]) -> str:
    """yam_hdf5 | mixed | other。"""
    names = [name for name in names if not is_generated_preview_name(name)]
    robot = [name for name in names if is_robot_filename(name)]
    other = [name for name in names if not is_robot_filename(name)]
    if robot and other:
        return "mixed"
    if robot:
        return "yam_hdf5"
    return "other"


def find_episode_dirs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    seen: set[Path] = set()
    for info in sorted(root.rglob("info.yaml")) + sorted(root.rglob("info.yml")):
        directory = info.parent.resolve()
        if directory in seen:
            continue
        seen.add(directory)
        if high_cam_path(directory) is not None:
            found.append(directory)
    return found


def high_cam_path(episode_dir: Path) -> Path | None:
    for name in ("high_cam.hdf5", "high_cam.h5"):
        path = episode_dir / name
        if path.is_file():
            return path
    return None


def require_yam_episodes(root: Path) -> list[Path]:
    episodes = find_episode_dirs(root)
    if not episodes:
        raise RobotImportError(
            "不是完整 YAM episode：同一目录需要 info.yaml 和 high_cam.hdf5。"
            "请上传一集目录、多集 zip，或最小包（info.yaml + high_cam.hdf5）。不要只丢一个 hdf5。"
        )
    return episodes
