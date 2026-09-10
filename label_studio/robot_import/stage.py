"""把上传文件拼成只读目录。不改写用户原始字节。"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

from . import RobotImportError
from .detect import is_zip_name, original_relative_name, require_yam_episodes


def _safe_join(root: Path, relative: str) -> Path:
    dest = (root / relative).resolve()
    root_resolved = root.resolve()
    if dest != root_resolved and not str(dest).startswith(str(root_resolved) + os.sep):
        raise RobotImportError(f"zip 含非法路径: {relative}")
    return dest


def extract_zip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                _safe_join(dest, info.filename)
            zf.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise RobotImportError("不是合法 zip") from exc


def copy_named_bytes(dest_dir: Path, filename: str, stream: BinaryIO) -> Path:
    relative = original_relative_name(filename)
    target = _safe_join(dest_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        shutil.copyfileobj(stream, out)
    return target


def stage_named_files(dest_dir: Path, files: Iterable[tuple[str, Path]]) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied_any = False
    for original_name, path in files:
        if is_zip_name(original_name):
            extract_zip(path, dest_dir)
            copied_any = True
            continue
        with path.open("rb") as stream:
            copy_named_bytes(dest_dir, original_name, stream)
        copied_any = True
    if not copied_any:
        raise RobotImportError("没有可拼装的 HDF5 文件")
    require_yam_episodes(dest_dir)
    return dest_dir
