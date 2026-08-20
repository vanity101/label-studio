"""识别 RLDS 上传批次。不依赖 tensorflow / Django。"""

from __future__ import annotations

from pathlib import Path

from . import RldsDecodeError

RLDS_META_NAMES = frozenset({"dataset_info.json", "features.json"})


def _as_path(name: str) -> Path:
    return Path(str(name).replace("\\", "/"))


def basename(name: str) -> str:
    return _as_path(name).name


def is_tfrecord_name(name: str) -> bool:
    return ".tfrecord" in basename(name).lower()


def is_zip_name(name: str) -> bool:
    return basename(name).lower().endswith(".zip")


def is_rlds_meta_name(name: str) -> bool:
    return basename(name).lower() in RLDS_META_NAMES


def is_rlds_filename(name: str) -> bool:
    return is_tfrecord_name(name) or is_zip_name(name) or is_rlds_meta_name(name)


def is_supported_upload_name(name: str, extra_extensions: set[str]) -> bool:
    """extra_extensions 形如 {'.mp4', '.json'}（含点、小写）。"""
    if is_tfrecord_name(name) or is_zip_name(name):
        return True
    ext = _as_path(name).suffix.lower()
    return ext in extra_extensions


def strip_upload_uuid_prefix(stored_name: str) -> str:
    """去掉 LS upload_name_generator 的 8 位 uuid 前缀。"""
    name = basename(stored_name)
    if len(name) > 9 and name[8] == "-" and all(ch in "0123456789abcdef" for ch in name[:8]):
        return name[9:]
    return name


def classify_upload_names(names: list[str]) -> str:
    """rlds | mixed | other。"""
    rlds = [name for name in names if is_rlds_filename(name)]
    other = [name for name in names if not is_rlds_filename(name)]
    if rlds and other:
        return "mixed"
    if rlds:
        return "rlds"
    return "other"


def has_tfrecord(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return any(path.is_file() and ".tfrecord" in path.name.lower() for path in directory.iterdir())


def find_bronze_root(root: Path) -> Path | None:
    """在解压/拼好的目录树里找同时含 dataset_info.json、features.json、tfrecord 的目录。"""
    if not root.is_dir():
        return None
    candidates = [root, *sorted({path.parent for path in root.rglob("dataset_info.json")})]
    seen: set[Path] = set()
    for directory in candidates:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if (
            (resolved / "dataset_info.json").is_file()
            and (resolved / "features.json").is_file()
            and has_tfrecord(resolved)
        ):
            return resolved
    return None


def require_complete_rlds(root: Path) -> Path:
    bronze = find_bronze_root(root)
    if bronze is None:
        raise RldsDecodeError(
            "不是完整 RLDS 数据集：需要同一目录下的 dataset_info.json、features.json 和 *.tfrecord*。"
            "请上传完整的 1.0.0 目录或 zip，不要只丢一个 shard。"
        )
    return bronze
