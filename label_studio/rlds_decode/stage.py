"""把上传文件拼成只读 Bronze 目录。不改写用户原始字节（拷贝后另存）。"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterable

from . import RldsDecodeError
from .detect import is_zip_name, require_complete_rlds


def _safe_join(root: Path, relative: str) -> Path:
    dest = (root / relative).resolve()
    root_resolved = root.resolve()
    if dest != root_resolved and not str(dest).startswith(str(root_resolved) + os.sep):
        raise RldsDecodeError(f"zip 含非法路径: {relative}")
    return dest


def extract_zip(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                _safe_join(dest, info.filename)
            zf.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise RldsDecodeError("不是合法 zip") from exc


def copy_named_bytes(dest_dir: Path, filename: str, stream: BinaryIO) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / Path(filename.replace("\\", "/")).name
    with target.open("wb") as out:
        shutil.copyfileobj(stream, out)
    return target


def stage_named_files(dest_dir: Path, files: Iterable[tuple[str, Path]]) -> Path:
    """files: (原始文件名, 本地路径)。zip 会解压；其余按 basename 拷进 dest_dir。"""
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
        raise RldsDecodeError("没有可拼装的 RLDS 文件")
    return require_complete_rlds(dest_dir)
