"""Django Import 拦截：FileUpload 批次 → YAM HDF5 / LeRobot 任务。"""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from . import RobotDependencyError, RobotImportError
from .detect import (
    classify_upload_names,
    is_generated_preview_name,
    is_zip_name,
    original_relative_name,
    strip_upload_uuid_prefix,
)
from .lerobot_detect import classify_staged_root, resolve_lerobot_dataset_root
from .stage import stage_named_files

logger = logging.getLogger(__name__)

_MIXED_UPLOAD_MSG = (
    "机器人数据集不能与其它类型文件混传。请单独上传 YAM episode 目录、zip 或最小包，"
    "或 LeRobot 目录/zip，不要与 mp4 或 json 混传。"
)
_UNRECOGNIZED_MSG = (
    "无法识别机器人数据集：请上传 YAM episode（info.yaml + high_cam.hdf5）"
    "或 LeRobot 目录/zip（meta/info.json + data/*.parquet）。"
)
_CONTENT_MIXED_MSG = "不能在同一批次混传 YAM HDF5 与 LeRobot 数据集。"


try:
    from rest_framework.exceptions import APIException
except ImportError:  # eval / 无 Django

    class APIException(Exception):  # type: ignore[no-redef]
        status_code = 503
        default_code = "robot_import_unavailable"

        def __init__(self, detail: str = "", *args, **kwargs):
            self.detail = detail
            super().__init__(detail)


class RobotImportUnavailable(APIException):
    status_code = 503
    default_code = "robot_import_unavailable"



def original_upload_name(file_upload) -> str:
    stored = Path(file_upload.file.name).as_posix()
    return original_relative_name(stored)


def existing_episode_ids(project) -> set[str]:
    from tasks.models import Task

    found: set[str] = set()
    for data in Task.objects.filter(project=project).values_list("data", flat=True).iterator():
        if isinstance(data, dict):
            episode_id = data.get("episode_id")
            if episode_id:
                found.add(str(episode_id))
    return found


def looks_like_lerobot_upload(names: list[str]) -> bool:
    for name in names:
        base = Path(name).name.lower()
        if base.endswith((".parquet", ".jsonl")) or base == "info.json":
            return True
    return False


def should_intercept_robot_uploads(names: list[str]) -> bool:
    """True 表示走 robot_import；False 交给普通 Import。混传抛 RobotImportError。"""
    kind = classify_upload_names(names)
    if kind == "mixed":
        raise RobotImportError(_MIXED_UPLOAD_MSG)
    if kind == "yam_hdf5":
        return True
    return looks_like_lerobot_upload(names)


def route_staged_robot(bronze: Path) -> str:
    """yam_hdf5 | lerobot；empty/mixed 抛 RobotImportError。"""
    classified = classify_staged_root(bronze)
    if classified in {"yam_hdf5", "lerobot"}:
        return classified
    if classified == "mixed":
        raise RobotImportError(_CONTENT_MIXED_MSG)
    raise RobotImportError(_UNRECOGNIZED_MSG)


def _file_upload_to_path(file_upload, scratch: Path) -> Path:
    field = file_upload.file
    try:
        path = Path(field.path)
        if path.is_file():
            return path
    except (NotImplementedError, ValueError, OSError):
        pass
    dest = scratch / strip_upload_uuid_prefix(Path(field.name).name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with field.open("rb") as src, dest.open("wb") as out:
        shutil.copyfileobj(src, out)
    return dest


def _attach_preview(user, project, episode_id: str, preview: Path):
    from django.core.files import File
    from data_import.models import FileUpload

    with preview.open("rb") as fh:
        upload = FileUpload(user=user, project=project, file=File(fh, name=f"{episode_id}-preview.mp4"))
        upload.save()
    return upload


def try_load_robot_tasks(project, file_uploads: list) -> tuple[list, dict, set] | None:
    from django.conf import settings
    from rest_framework.exceptions import ValidationError

    if not file_uploads:
        return None

    file_uploads = [item for item in file_uploads if not is_generated_preview_name(original_upload_name(item))]
    names = [original_upload_name(item) for item in file_uploads]
    try:
        if not should_intercept_robot_uploads(names):
            return None
    except RobotImportError as exc:
        raise ValidationError(str(exc)) from exc

    user = file_uploads[0].user
    import_id = uuid.uuid4().hex[:12]
    bronze_root = Path(settings.MEDIA_ROOT) / "robot_bronze" / str(project.id) / import_id
    preview_root = bronze_root / "media"
    bronze_root.mkdir(parents=True, exist_ok=True)
    source_kind = "yam_hdf5"

    try:
        with tempfile.TemporaryDirectory(prefix="ls-robot-src-") as tmp:
            scratch = Path(tmp)
            pairs = [(original_upload_name(item), _file_upload_to_path(item, scratch)) for item in file_uploads]
            bronze = stage_named_files(bronze_root / "bronze", pairs)
            classified = classify_staged_root(bronze)
            zip_only = bool(names) and all(
                is_zip_name(name) or is_generated_preview_name(name) for name in names
            )
            if classified == "empty" and zip_only:
                return None
            source_kind = route_staged_robot(bronze)
            from .import_batch import decode_bronze_to_tasks_isolated, decode_lerobot_to_tasks_isolated

            decode_root = resolve_lerobot_dataset_root(bronze) if source_kind == "lerobot" else bronze
            decode = (
                decode_lerobot_to_tasks_isolated if source_kind == "lerobot" else decode_bronze_to_tasks_isolated
            )
            result = decode(
                decode_root,
                preview_root,
                existing_episode_ids=existing_episode_ids(project),
            )
    except RobotDependencyError as exc:
        raise RobotImportUnavailable(detail=str(exc)) from exc
    except RobotImportError as exc:
        raise ValidationError(str(exc)) from exc

    tasks: list[dict] = []
    for item in result.tasks:
        data = dict(item["data"])
        preview = Path(data["video"])
        upload = _attach_preview(user, project, data["episode_id"], preview)
        data["video"] = upload.url
        tasks.append({"data": data, "file_upload_id": upload.id})

    label = "LeRobot" if source_kind == "lerobot" else "HDF5"
    ext_key = ".parquet" if source_kind == "lerobot" else ".hdf5"
    if not tasks:
        if result.skipped_episode_ids:
            raise ValidationError(
                "没有新的 episode 可导入（已存在的 episode_id 已跳过）: "
                + ", ".join(result.skipped_episode_ids[:8])
            )
        raise ValidationError(f"{label} 数据集里没有可导入的 episode")

    logger.info(
        "%s import project=%s tasks=%s skipped=%s truncated=%s",
        label,
        project.id,
        len(tasks),
        len(result.skipped_episode_ids),
        result.truncated,
    )
    fields = {"video", "episode_id", "source_type"}
    return tasks, {ext_key: len(tasks)}, fields
