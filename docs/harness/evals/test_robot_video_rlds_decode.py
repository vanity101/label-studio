"""Eval for RLDS / TFRecord → MP4 import. Contract: robot-video-rlds-decode.md"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video"
LS = ROOT / "label_studio"
EVALS = Path(__file__).resolve().parent


def _reexec_venv_if_needed() -> None:
    """物化需要 tensorflow；仓库 .venv 已装 [rlds] 时用它重跑。"""
    import os

    venv_python = ROOT / ".venv" / "bin" / "python"
    if Path(sys.executable).resolve() == venv_python.resolve():
        return
    try:
        import tensorflow_datasets  # noqa: F401
        return
    except ImportError:
        pass
    if venv_python.is_file():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


_reexec_venv_if_needed()
for path in (str(LS), str(OVERLAY), str(EVALS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import check_overlay as overlay  # noqa: E402
from rlds_decode.detect import (  # noqa: E402
    classify_upload_names,
    is_supported_upload_name,
    require_complete_rlds,
    strip_upload_uuid_prefix,
)
from rlds_decode.import_batch import skip_existing  # noqa: E402
from rlds_decode.stage import stage_named_files  # noqa: E402
from rlds_decode import RldsDecodeError  # noqa: E402


def _write_fake_bronze(root: Path) -> Path:
    bronze = root / "1.0.0"
    bronze.mkdir(parents=True)
    (bronze / "dataset_info.json").write_text("{}", encoding="utf-8")
    (bronze / "features.json").write_text("{}", encoding="utf-8")
    (bronze / "demo-train.tfrecord-00000-of-00001").write_bytes(b"not-a-real-tfrecord")
    return bronze


def test_classify_names_and_supported_extensions():
    shard = "utokyo-train.tfrecord-00000-of-00001"
    assert classify_upload_names([shard, "dataset_info.json", "features.json"]) == "rlds"
    assert classify_upload_names(["dataset.zip"]) == "rlds"
    assert classify_upload_names(["clip.mp4"]) == "other"
    assert classify_upload_names(["dataset.zip", "clip.mp4"]) == "mixed"
    extra = {".mp4", ".json"}
    assert is_supported_upload_name(shard, extra)
    assert is_supported_upload_name("dataset.zip", extra)
    assert is_supported_upload_name("clip.mp4", extra)
    assert not is_supported_upload_name("notes.exe", extra)
    assert strip_upload_uuid_prefix("6b25fc23-dataset_info.json") == "dataset_info.json"
    assert strip_upload_uuid_prefix("features.json") == "features.json"


def test_orphan_tfrecord_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "only.tfrecord-00000-of-00001").write_bytes(b"x")
        try:
            require_complete_rlds(root)
        except RldsDecodeError as exc:
            text = str(exc)
            assert "dataset_info" in text or "features" in text
        else:
            raise AssertionError("孤 tfrecord 应失败")


def test_stage_zip_finds_bronze():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bronze = _write_fake_bronze(root / "src")
        archive = root / "rlds.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in bronze.iterdir():
                zf.write(path, arcname=f"1.0.0/{path.name}")
        dest = root / "staged"
        found = stage_named_files(dest, [("rlds.zip", archive)])
        assert (found / "dataset_info.json").is_file()
        assert (found / "features.json").is_file()
        assert any(".tfrecord" in p.name for p in found.iterdir())


def test_skip_existing_episode_ids():
    pending, skipped = skip_existing(["a", "b", "c"], {"b"})
    assert pending == ["a", "c"]
    assert skipped == ["b"]


def test_import_jsx_allows_tfrecord_and_zip():
    text = (
        ROOT / "web" / "apps" / "labelstudio" / "src" / "pages" / "CreateProject" / "Import" / "Import.jsx"
    ).read_text(encoding="utf-8")
    assert "isSupportedImportFile" in text
    assert ".tfrecord" in text
    assert '"zip"' in text or "'zip'" in text
    assert "complete RLDS" in text or "1.0.0" in text


def test_uploader_and_models_hook_rlds():
    uploader = (LS / "data_import" / "uploader.py").read_text(encoding="utf-8")
    models = (LS / "data_import" / "models.py").read_text(encoding="utf-8")
    ls_import = (LS / "rlds_decode" / "ls_import.py").read_text(encoding="utf-8")
    assert "is_supported_upload_name" in uploader
    assert "try_load_rlds_tasks" in models
    assert "FastAPI" not in ls_import
    assert "uvicorn" not in ls_import
    assert "source_type" in ls_import
    assert "episode_id" in ls_import


def test_dockerfile_ffmpeg_and_rlds_copy():
    text = (OVERLAY / "Dockerfile").read_text(encoding="utf-8")
    assert "heartexlabs/label-studio" in text
    assert "ffmpeg" in text
    assert "apk add" in text
    runtime = text.split("FROM heartexlabs/label-studio", 1)[-1]
    assert "apt-get install" not in runtime
    assert "apt-get update" not in runtime
    assert "tensorflow" in text
    assert "label_studio/rlds_decode" in text
    assert "pypi.tuna.tsinghua.edu.cn" in text
    assert "NO_GCE_CHECK" in text
    assert "DATA_UPLOAD_MAX_MEMORY_SIZE" in text
    assert "RLDS_IMPORT_MAX_EPISODES" in text
    assert "python:3.12-slim-bookworm" in text
    assert "RLDS_PYTHON" in text
    assert "rlds_python.sh" in text
    assert "python:3.12-slim-bookworm" in text
    assert "RLDS_PYTHON" in text
    assert "rlds_python.sh" in text


def test_start_script_rlds_runtime_env():
    text = (OVERLAY / "start_label_studio.py").read_text(encoding="utf-8")
    assert "DATA_UPLOAD_MAX_MEMORY_SIZE" in text
    assert "NO_GCE_CHECK" in text
    assert "RLDS_IMPORT_MAX_EPISODES" in text
    assert "rlds_decode" in text
    assert "--local" in text
    assert "8081" in text
    assert "DEFAULT_PORT = 8081" in text
    assert "--docker" in text
    ls_import = (LS / "rlds_decode" / "ls_import.py").read_text(encoding="utf-8")
    assert "decode_bronze_to_tasks_isolated" in ls_import
    batch = (LS / "rlds_decode" / "import_batch.py").read_text(encoding="utf-8")
    assert "RLDS_PYTHON" in batch
    worker = (LS / "rlds_decode" / "worker.py").read_text(encoding="utf-8")
    assert "decode_bronze_to_tasks" in worker
    seed = (OVERLAY / "seed_project.py").read_text(encoding="utf-8")
    assert "LABEL_STUDIO_RLDS_CONFIG" in seed
    assert "single-view-rlds.xml" in seed


def test_pyproject_rlds_extra():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "rlds" in text
    assert "tensorflow-datasets" in text
    assert "Pillow" in text


def test_single_view_rlds_xml():
    overlay.check_single_view_rlds(overlay.parse_config(overlay.SINGLE_VIEW_RLDS))
    overlay.check_single_view(overlay.parse_config(overlay.SINGLE_VIEW))


def test_previous_overlay_eval_still_holds():
    errors = overlay.run_all()
    assert not errors, errors


def _require_materialize_deps() -> None:
    try:
        import tensorflow_datasets  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise AssertionError(
            "RLDS 物化测试需要 tensorflow / tensorflow-datasets / Pillow。"
            "请安装: pip install 'label-studio[rlds]' -i https://pypi.tuna.tsinghua.edu.cn/simple"
        ) from exc
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AssertionError("RLDS 物化测试需要系统 ffmpeg / ffprobe")


def _tfrecord_fingerprints(bronze: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(bronze.glob("*.tfrecord*")):
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def test_materialize_frames_and_task_shape_and_skip():
    _require_materialize_deps()
    from rlds_fixture import build_mini_fridge
    from rlds_decode.import_batch import decode_bronze_to_tasks
    from rlds_decode.rlds import list_episodes

    with tempfile.TemporaryDirectory() as tmp:
        bronze = Path(build_mini_fridge(tmp))
        before = _tfrecord_fingerprints(bronze)
        listed = list_episodes(bronze)
        assert listed, "合成 RLDS 应列出 episode"
        preview_root = Path(tmp) / "media"
        first = decode_bronze_to_tasks(bronze, preview_root, max_episodes=16)
        assert len(first.tasks) == len(listed)
        for task in first.tasks:
            data = task["data"]
            assert data["source_type"] == "rlds"
            assert data["episode_id"]
            assert str(data["video"]).endswith(".mp4")
            assert Path(data["video"]).is_file()
        from rlds_decode.materialize import count_mp4_frames

        for task, meta in zip(first.tasks, listed):
            frames = count_mp4_frames(Path(task["data"]["video"]))
            assert frames == meta["num_frames"] == task["data"]["num_frames"]

        assert _tfrecord_fingerprints(bronze) == before

        existing = {task["data"]["episode_id"] for task in first.tasks}
        again = decode_bronze_to_tasks(
            bronze, preview_root, existing_episode_ids=existing, max_episodes=16
        )
        assert again.tasks == []
        assert set(again.skipped_episode_ids) == existing

        truncated = decode_bronze_to_tasks(
            bronze, Path(tmp) / "media2", existing_episode_ids=set(), max_episodes=1
        )
        assert len(truncated.tasks) == 1
        assert truncated.truncated is True or len(listed) == 1


def _run_standalone() -> int:
    tests = [
        test_classify_names_and_supported_extensions,
        test_orphan_tfrecord_is_rejected,
        test_stage_zip_finds_bronze,
        test_skip_existing_episode_ids,
        test_import_jsx_allows_tfrecord_and_zip,
        test_uploader_and_models_hook_rlds,
        test_dockerfile_ffmpeg_and_rlds_copy,
        test_start_script_rlds_runtime_env,
        test_pyproject_rlds_extra,
        test_single_view_rlds_xml,
        test_previous_overlay_eval_still_holds,
        test_materialize_frames_and_task_shape_and_skip,
    ]
    failed = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed.append(test.__name__)
            print(f"FAIL {test.__name__}: {exc}")
            traceback.print_exc()
    total = len(tests)
    passed = total - len(failed)
    print(f"{passed}/{total} passed, pass_rate={passed / total:.2f}")
    if failed:
        print("Critical failures:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
