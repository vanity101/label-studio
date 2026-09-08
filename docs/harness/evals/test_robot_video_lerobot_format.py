"""Eval for LeRobot v2/v2.1 format parse (S1-T1). Spec FR-002, FR-005, ASM-001…003."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LS = ROOT / "label_studio"
EVALS = Path(__file__).resolve().parent
FIXTURE = EVALS / "fixtures" / "lerobot_mini"

for path in (str(LS), str(EVALS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from robot_import import RobotImportError  # noqa: E402
from robot_import.lerobot_format import (  # noqa: E402
    list_episodes,
    parse_info,
    pick_video_feature,
)


def _copy_fixture(dest: Path) -> Path:
    shutil.copytree(FIXTURE, dest)
    return dest


def test_fixture_layout_exists():
    assert (FIXTURE / "meta" / "info.json").is_file()
    assert (
        FIXTURE
        / "videos"
        / "chunk-000"
        / "observation.images.cam_high"
        / "episode_000000.mp4"
    ).is_file()
    info = json.loads((FIXTURE / "meta" / "info.json").read_text(encoding="utf-8"))
    assert str(info["codebase_version"]).startswith("v2")


def test_parse_info_v21_and_pick_cam_high():
    with tempfile.TemporaryDirectory() as tmp:
        root = _copy_fixture(Path(tmp) / "ds")
        parsed = parse_info(root)
        assert parsed["codebase_version"] == "v2.1"
        assert parsed["video_feature"] == "observation.images.cam_high"
        assert parsed["fps"] == 30
        assert parsed["root"] == root
        assert pick_video_feature(parsed["info"]) == "observation.images.cam_high"


def test_list_episodes_stable_id_and_video_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = _copy_fixture(Path(tmp) / "ds")
        episodes = list_episodes(root)
        assert len(episodes) == 1
        item = episodes[0]
        assert item["episode_id"] == "episode_000000"
        assert item["index"] == 0
        assert item["camera"] == "cam_high"
        assert item["fps"] == 30
        assert item["video_path"].is_file()
        assert item["video_path"].name == "episode_000000.mp4"
        again = list_episodes(root)
        assert again[0]["episode_id"] == item["episode_id"]


def test_pick_video_feature_falls_back_to_laptop_then_first():
    laptop_only = {
        "features": {
            "observation.images.wrist": {"dtype": "video"},
            "observation.images.laptop": {"dtype": "video"},
        }
    }
    assert pick_video_feature(laptop_only) == "observation.images.laptop"
    first_only = {
        "features": {
            "observation.images.wrist": {"dtype": "video"},
            "action": {"dtype": "float32"},
        }
    }
    assert pick_video_feature(first_only) == "observation.images.wrist"
    assert pick_video_feature({"features": {"action": {"dtype": "float32"}}}) == ""
    assert pick_video_feature({}) == ""


def test_reject_missing_info_json():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "empty"
        root.mkdir()
        try:
            parse_info(root)
        except RobotImportError as exc:
            assert "info.json" in str(exc)
        else:
            raise AssertionError("expected RobotImportError for missing info.json")


def test_reject_non_v2_codebase():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "v1"
        meta = root / "meta"
        meta.mkdir(parents=True)
        (meta / "info.json").write_text(
            json.dumps(
                {
                    "codebase_version": "v1.0",
                    "fps": 30,
                    "features": {"observation.images.cam_high": {"dtype": "video"}},
                }
            ),
            encoding="utf-8",
        )
        try:
            parse_info(root)
        except RobotImportError as exc:
            assert "v2" in str(exc)
        else:
            raise AssertionError("expected RobotImportError for v1")


def test_list_episodes_allows_missing_videos_and_null_video_path():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "parquet_only"
        meta = root / "meta"
        meta.mkdir(parents=True)
        (root / "data").mkdir()
        (root / "data" / "episode_000000.parquet").write_bytes(b"PAR1")
        (meta / "info.json").write_text(
            json.dumps(
                {
                    "codebase_version": "v2.1",
                    "fps": 10,
                    "total_episodes": 1,
                    "video_path": None,
                    "features": {"action": {"dtype": "float32", "shape": [7]}},
                }
            ),
            encoding="utf-8",
        )
        parsed = parse_info(root)
        assert parsed["video_feature"] == ""
        assert parsed["fps"] == 10
        episodes = list_episodes(root)
        assert len(episodes) == 1
        assert episodes[0]["episode_id"] == "episode_000000"
        assert episodes[0]["video_path"] is None

        with_null = _copy_fixture(Path(tmp) / "null_path")
        (
            with_null
            / "videos"
            / "chunk-000"
            / "observation.images.cam_high"
            / "episode_000000.mp4"
        ).unlink()
        info_path = with_null / "meta" / "info.json"
        info = json.loads(info_path.read_text(encoding="utf-8"))
        info["video_path"] = None
        info_path.write_text(json.dumps(info), encoding="utf-8")
        listed = list_episodes(with_null)
        assert listed[0]["episode_id"] == "episode_000000"
        assert listed[0]["video_path"] is None


def _run_standalone() -> int:
    tests = [
        test_fixture_layout_exists,
        test_parse_info_v21_and_pick_cam_high,
        test_list_episodes_stable_id_and_video_path,
        test_pick_video_feature_falls_back_to_laptop_then_first,
        test_reject_missing_info_json,
        test_reject_non_v2_codebase,
        test_list_episodes_allows_missing_videos_and_null_video_path,
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
