"""Eval for Import wiring: jsx copy + ls_import HDF5/LeRobot routing."""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LS = ROOT / "label_studio"
EVALS = Path(__file__).resolve().parent
IMPORT_JSX = ROOT / "web" / "apps" / "labelstudio" / "src" / "pages" / "CreateProject" / "Import" / "Import.jsx"
SETTINGS = LS / "core" / "settings" / "base.py"


def _reexec_venv_if_needed() -> None:
    import os

    venv_python = ROOT / ".venv" / "bin" / "python"
    if Path(sys.executable).resolve() == venv_python.resolve():
        return
    if venv_python.is_file():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


_reexec_venv_if_needed()
if str(LS) not in sys.path:
    sys.path.insert(0, str(LS))

from robot_import import RobotImportError  # noqa: E402
from robot_import.ls_import import (  # noqa: E402
    looks_like_lerobot_upload,
    route_staged_robot,
    should_intercept_robot_uploads,
)
from robot_import.stage import stage_named_files  # noqa: E402


def _write_yam_episode(root: Path, episode_id: str = "episode_000000") -> Path:
    episode = root / episode_id
    episode.mkdir(parents=True)
    (episode / "info.yaml").write_text("data_schema_version: 3\n", encoding="utf-8")
    (episode / "high_cam.hdf5").write_bytes(b"HDF5")
    return episode


def _write_lerobot_root(root: Path) -> Path:
    meta = root / "meta"
    meta.mkdir(parents=True)
    payload = {
        "codebase_version": "v2.1",
        "fps": 10,
        "video_path": None,
        "total_episodes": 1,
        "features": {},
    }
    (meta / "info.json").write_text(json.dumps(payload), encoding="utf-8")
    (meta / "episodes.jsonl").write_text('{"episode_index": 0, "length": 1}\n', encoding="utf-8")
    data = root / "data"
    data.mkdir(parents=True)
    (data / "episode_000000.parquet").write_bytes(b"PAR1")
    return root


def test_import_jsx_lerobot_copy_and_extensions():
    text = IMPORT_JSX.read_text(encoding="utf-8")
    assert "LeRobot will be added later" not in text
    assert "parquet" in text
    assert "jsonl" in text
    assert "LeRobot" in text
    assert "directory or zip" in text
    assert "Do not mix with" in text
    assert "mp4" in text
    assert "json" in text
    settings = SETTINGS.read_text(encoding="utf-8")
    assert "'.parquet'" in settings
    assert "'.jsonl'" in settings


def test_ls_import_source_routes_classify_and_decode():
    text = (LS / "robot_import" / "ls_import.py").read_text(encoding="utf-8")
    assert "classify_staged_root" in text
    assert "decode_lerobot_to_tasks_isolated" in text
    assert "decode_bronze_to_tasks_isolated" in text
    assert "route_staged_robot" in text
    stage = (LS / "robot_import" / "stage.py").read_text(encoding="utf-8")
    assert "require_yam_episodes" not in stage


def test_name_gate_intercepts_lerobot_and_rejects_mix():
    assert should_intercept_robot_uploads(["meta/info.json", "data/episode_000000.parquet"])
    assert looks_like_lerobot_upload(["chunk/episode_000000.parquet"])
    assert should_intercept_robot_uploads(["yam.zip"])
    assert not should_intercept_robot_uploads(["notes.txt"])
    assert not should_intercept_robot_uploads(["tasks.json"])
    try:
        should_intercept_robot_uploads(["high_cam.hdf5", "clip.mp4"])
    except RobotImportError as exc:
        assert "混传" in str(exc)
    else:
        raise AssertionError("hdf5 + mp4 应拒绝")


def test_stage_then_route_lerobot_without_yam_require():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        dataset = _write_lerobot_root(root / "src")
        dest = root / "staged"
        pairs = []
        for path in dataset.rglob("*"):
            if path.is_file():
                pairs.append((str(path.relative_to(dataset.parent)), path))
        found = stage_named_files(dest, pairs)
        assert route_staged_robot(found) == "lerobot"


def test_stage_zip_still_routes_yam():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        episode = _write_yam_episode(root / "src")
        archive = root / "yam.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for path in episode.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=f"{episode.name}/{path.name}")
        dest = root / "staged"
        found = stage_named_files(dest, [("yam.zip", archive)])
        assert route_staged_robot(found) == "yam_hdf5"


def test_empty_stage_is_unrecognized():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        only = root / "orphan.parquet"
        only.write_bytes(b"PAR1")
        dest = root / "staged"
        found = stage_named_files(dest, [("orphan.parquet", only)])
        try:
            route_staged_robot(found)
        except RobotImportError as exc:
            assert "LeRobot" in str(exc) or "无法识别" in str(exc)
        else:
            raise AssertionError("孤 parquet 应无法分流")


def _run_standalone() -> int:
    tests = [
        test_import_jsx_lerobot_copy_and_extensions,
        test_ls_import_source_routes_classify_and_decode,
        test_name_gate_intercepts_lerobot_and_rejects_mix,
        test_stage_then_route_lerobot_without_yam_require,
        test_stage_zip_still_routes_yam,
        test_empty_stage_is_unrecognized,
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
