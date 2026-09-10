"""Eval for YAM HDF5 → MP4 import. Contract: robot-video-hdf5-import.md"""

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
    import os

    venv_python = ROOT / ".venv" / "bin" / "python"
    if Path(sys.executable).resolve() == venv_python.resolve():
        return
    try:
        import h5py  # noqa: F401
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
from robot_import import RobotImportError  # noqa: E402
from robot_import.detect import (  # noqa: E402
    classify_upload_names,
    is_supported_upload_name,
    require_yam_episodes,
    strip_upload_uuid_prefix,
)
from robot_import.import_batch import skip_existing  # noqa: E402
from robot_import.stage import stage_named_files  # noqa: E402


def _write_mini_episode(root: Path, episode_id: str = "episode_000000", frames: int = 3) -> Path:
    import numpy as np
    import h5py

    episode = root / episode_id
    episode.mkdir(parents=True)
    (episode / "info.yaml").write_text(
        "data_schema_version: 3\nstorage:\n  camera_files:\n    high_cam: high_cam.hdf5\n",
        encoding="utf-8",
    )
    cam = episode / "high_cam.hdf5"
    rgb = np.zeros((frames, 180, 320, 3), dtype=np.uint8)
    for index in range(frames):
        rgb[index, :, :, 0] = 40 + index * 40
        rgb[index, :, :, 1] = 80
        rgb[index, :, :, 2] = 160
    with h5py.File(cam, "w") as handle:
        group = handle.create_group("rgb")
        group.attrs["requested_hz"] = 30
        group.create_dataset("data", data=rgb)
    return episode


def test_classify_names_and_supported_extensions():
    assert classify_upload_names(["info.yaml", "high_cam.hdf5"]) == "yam_hdf5"
    assert classify_upload_names(["dataset.zip"]) == "yam_hdf5"
    assert classify_upload_names(["clip.mp4"]) == "other"
    assert classify_upload_names(["high_cam.hdf5", "clip.mp4"]) == "mixed"
    assert classify_upload_names(["pack.zip", "episode_000000-preview.mp4"]) == "yam_hdf5"
    extra = {".mp4", ".json"}
    assert is_supported_upload_name("high_cam.hdf5", extra)
    assert is_supported_upload_name("info.yaml", extra)
    assert is_supported_upload_name("pack.zip", extra)
    assert is_supported_upload_name("COMPLETE", extra)
    assert is_supported_upload_name("clip.mp4", extra)
    assert not is_supported_upload_name("notes.exe", extra)
    assert strip_upload_uuid_prefix("6b25fc23-info.yaml") == "info.yaml"


def test_orphan_hdf5_is_rejected():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "only.hdf5").write_bytes(b"x")
        try:
            require_yam_episodes(root)
        except RobotImportError as exc:
            text = str(exc)
            assert "info.yaml" in text
        else:
            raise AssertionError("孤 hdf5 应失败")


def test_stage_zip_finds_episode():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        episode = _write_mini_episode(root / "src")
        archive = root / "yam.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in episode.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=f"{episode.name}/{path.name}")
        dest = root / "staged"
        found = stage_named_files(dest, [("yam.zip", archive)])
        assert (found / "episode_000000" / "info.yaml").is_file()
        assert (found / "episode_000000" / "high_cam.hdf5").is_file()


def test_skip_existing_episode_ids():
    pending, skipped = skip_existing(["a", "b", "c"], {"b"})
    assert pending == ["a", "c"]
    assert skipped == ["b"]


def test_import_jsx_lists_hdf5_not_rlds():
    text = (
        ROOT / "web" / "apps" / "labelstudio" / "src" / "pages" / "CreateProject" / "Import" / "Import.jsx"
    ).read_text(encoding="utf-8")
    assert "isSupportedImportFile" in text
    assert "hdf5" in text
    assert "high_cam.hdf5" in text
    assert "tfrecord" not in text.lower()
    assert "complete RLDS" not in text
    assert "openFilePicker" in text
    assert 'display: "none"' not in text


def test_uploader_and_models_hook_robot_import():
    uploader = (LS / "data_import" / "uploader.py").read_text(encoding="utf-8")
    models = (LS / "data_import" / "models.py").read_text(encoding="utf-8")
    ls_import = (LS / "robot_import" / "ls_import.py").read_text(encoding="utf-8")
    assert "is_supported_upload_name" in uploader
    assert "robot_import.detect" in uploader
    assert "try_load_robot_tasks" in models
    assert "try_load_rlds_tasks" not in models
    assert "FastAPI" not in ls_import
    assert "source_type" in ls_import
    assert "episode_id" in ls_import


def test_dockerfile_h5py_and_robot_import():
    text = (OVERLAY / "Dockerfile").read_text(encoding="utf-8")
    assert "heartexlabs/label-studio" in text
    assert "ffmpeg" in text
    assert "apk add" in text
    runtime = text.split("FROM heartexlabs/label-studio", 1)[-1]
    assert "apt-get install" not in runtime
    assert "h5py" in text
    assert "label_studio/robot_import" in text
    assert "pypi.tuna.tsinghua.edu.cn" in text
    assert "DATA_UPLOAD_MAX_MEMORY_SIZE" in text
    assert "ROBOT_IMPORT_PYTHON" in text
    assert "python:3.12-slim-bookworm" in text
    start = (OVERLAY / "start_label_studio.py").read_text(encoding="utf-8")
    assert "ROBOT_IMPORT_MAX_EPISODES" in text or "ROBOT_IMPORT_MAX_EPISODES" in start
    assert "robot_import" in start
    assert "--local" in start


def test_single_view_is_30fps():
    overlay.check_single_view(overlay.parse_config(overlay.SINGLE_VIEW))


def test_previous_overlay_eval_still_holds():
    errors = overlay.run_all()
    assert not errors, errors


def _require_materialize_deps() -> None:
    try:
        import h5py  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise AssertionError(
            "HDF5 物化测试需要 h5py / Pillow。"
            "请安装: pip install h5py Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple "
            "--trusted-host pypi.tuna.tsinghua.edu.cn"
        ) from exc
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AssertionError("HDF5 物化测试需要系统 ffmpeg / ffprobe")


def test_materialize_frames_and_task_shape_and_skip():
    _require_materialize_deps()
    from robot_import.import_batch import decode_bronze_to_tasks
    from robot_import.materialize import count_mp4_frames

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        episode = _write_mini_episode(root / "src", frames=4)
        before = hashlib.sha256((episode / "high_cam.hdf5").read_bytes()).hexdigest()
        preview_root = root / "media"
        first = decode_bronze_to_tasks(root / "src", preview_root, max_episodes=16)
        assert len(first.tasks) == 1
        data = first.tasks[0]["data"]
        assert data["source_type"] == "yam_hdf5"
        assert data["episode_id"] == "episode_000000"
        assert data["camera"] == "high_cam"
        assert data["fps"] == 30
        assert data["num_frames"] == 4
        assert str(data["video"]).endswith(".mp4")
        assert count_mp4_frames(Path(data["video"])) == 4
        after = hashlib.sha256((episode / "high_cam.hdf5").read_bytes()).hexdigest()
        assert after == before
        second = decode_bronze_to_tasks(
            root / "src",
            preview_root,
            existing_episode_ids={"episode_000000"},
        )
        assert second.tasks == []
        assert second.skipped_episode_ids == ["episode_000000"]


def _run_standalone() -> int:
    tests = [
        test_classify_names_and_supported_extensions,
        test_orphan_hdf5_is_rejected,
        test_stage_zip_finds_episode,
        test_skip_existing_episode_ids,
        test_import_jsx_lists_hdf5_not_rlds,
        test_uploader_and_models_hook_robot_import,
        test_dockerfile_h5py_and_robot_import,
        test_single_view_is_30fps,
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
