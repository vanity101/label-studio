"""Django Import 拦截：FileUpload 批次 → RLDS 任务。"""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files import File
from rest_framework.exceptions import APIException, ValidationError

from . import RldsDecodeError, RldsDependencyError
from .detect import classify_upload_names, strip_upload_uuid_prefix
from .import_batch import decode_bronze_to_tasks_isolated
from .stage import stage_named_files

logger = logging.getLogger(__name__)


class RldsUnavailable(APIException):
    status_code = 503
    default_code = "rlds_unavailable"


def original_upload_name(file_upload) -> str:
    """去掉 LS upload_name_generator 的 8 位 uuid 前缀，还原用户文件名。"""
    return strip_upload_uuid_prefix(Path(file_upload.file.name).name)


def existing_episode_ids(project) -> set[str]:
    from tasks.models import Task

    found: set[str] = set()
    for data in Task.objects.filter(project=project).values_list("data", flat=True).iterator():
        if isinstance(data, dict):
            episode_id = data.get("episode_id")
            if episode_id:
                found.add(str(episode_id))
    return found


def _file_upload_to_path(file_upload, scratch: Path) -> Path:
    field = file_upload.file
    try:
        path = Path(field.path)
        if path.is_file():
            return path
    except (NotImplementedError, ValueError, OSError):
        pass
    dest = scratch / original_upload_name(file_upload)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with field.open("rb") as src, dest.open("wb") as out:
        shutil.copyfileobj(src, out)
    return dest


def _attach_preview(user, project, episode_id: str, preview: Path):
    from data_import.models import FileUpload

    with preview.open("rb") as fh:
        upload = FileUpload(user=user, project=project, file=File(fh, name=f"{episode_id}-preview.mp4"))
        upload.save()
    return upload


def try_load_rlds_tasks(project, file_uploads: list) -> tuple[list, dict, set] | None:
    """若本批次是 RLDS 则返回 (tasks, formats, data_fields)；否则 None 走原导入。"""
    if not file_uploads:
        return None

    names = [original_upload_name(item) for item in file_uploads]
    kind = classify_upload_names(names)
    if kind == "other":
        return None
    if kind == "mixed":
        raise ValidationError("RLDS 导入不能与其它类型文件混传。请单独上传完整 RLDS 目录或 zip。")

    user = file_uploads[0].user
    import_id = uuid.uuid4().hex[:12]
    bronze_root = Path(settings.MEDIA_ROOT) / "rlds_bronze" / str(project.id) / import_id
    preview_root = bronze_root / "media"
    bronze_root.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="ls-rlds-src-") as tmp:
            scratch = Path(tmp)
            pairs = [(original_upload_name(item), _file_upload_to_path(item, scratch)) for item in file_uploads]
            bronze = stage_named_files(bronze_root / "bronze", pairs)
            result = decode_bronze_to_tasks_isolated(
                bronze,
                preview_root,
                existing_episode_ids=existing_episode_ids(project),
            )
    except RldsDependencyError as exc:
        raise RldsUnavailable(detail=str(exc)) from exc
    except RldsDecodeError as exc:
        raise ValidationError(str(exc)) from exc

    tasks: list[dict] = []
    for item in result.tasks:
        data = dict(item["data"])
        preview = Path(data["video"])
        upload = _attach_preview(user, project, data["episode_id"], preview)
        data["video"] = upload.url
        tasks.append({"data": data, "file_upload_id": upload.id})

    if not tasks:
        if result.skipped_episode_ids:
            raise ValidationError(
                "没有新的 episode 可导入（已存在的 episode_id 已跳过）: "
                + ", ".join(result.skipped_episode_ids[:8])
            )
        raise ValidationError("RLDS 数据集里没有可导入的 episode")

    logger.info(
        "RLDS import project=%s tasks=%s skipped=%s truncated=%s",
        project.id,
        len(tasks),
        len(result.skipped_episode_ids),
        result.truncated,
    )
    fields = {"video", "episode_id", "source_type"}
    return tasks, {".rlds": len(tasks)}, fields
