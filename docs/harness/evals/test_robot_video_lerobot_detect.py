"""Eval for staged-root content gate. Contract: robot-import-classify.md"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LS = ROOT / "label_studio"

if str(LS) not in sys.path:
    sys.path.insert(0, str(LS))

from robot_import.lerobot_detect import classify_staged_root  # noqa: E402


def _write_yam_episode(root: Path, episode_id: str = "episode_000000") -> Path:
    episode = root / episode_id
    episode.mkdir(parents=True)
    (episode / "info.yaml").write_text("data_schema_version: 3\n", encoding="utf-8")
    (episode / "high_cam.hdf5").write_bytes(b"HDF5")
    return episode


def _write_lerobot_root(
    root: Path,
    *,
    version: str = "v2.1",
    parquet: bool = True,
    total_episodes: int | None = 1,
    video_path=None,
) -> Path:
    meta = root / "meta"
    meta.mkdir(parents=True)
    payload = {
        "codebase_version": version,
        "fps": 30,
        "video_path": video_path,
        "features": {},
    }
    if total_episodes is not None:
        payload["total_episodes"] = total_episodes
    (meta / "info.json").write_text(json.dumps(payload), encoding="utf-8")
    if parquet:
        data = root / "data"
        data.mkdir(parents=True, exist_ok=True)
        (data / "episode_000000.parquet").write_bytes(b"PAR1")
    return root


def test_yam_episode_is_yam_hdf5():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_yam_episode(root)
        assert classify_staged_root(root) == "yam_hdf5"


def test_lerobot_without_videos_is_lerobot():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_lerobot_root(root, video_path=None)
        assert not (root / "videos").exists()
        assert classify_staged_root(root) == "lerobot"


def test_lerobot_nested_zip_layout_is_lerobot():
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp)
        dataset = staged / "lerobot_0907_test2"
        _write_lerobot_root(dataset, version="v2.1", video_path=None)
        assert classify_staged_root(staged) == "lerobot"


def test_yam_and_lerobot_together_is_mixed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_yam_episode(root)
        _write_lerobot_root(root / "lerobot")
        assert classify_staged_root(root) == "mixed"


def test_empty_dir_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        assert classify_staged_root(Path(tmp)) == "empty"


def test_images_only_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        images = root / "images"
        _write_yam_episode(images)
        _write_lerobot_root(images / "lerobot")
        assert classify_staged_root(root) == "empty"


def test_orphan_parquet_without_meta_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data = root / "data"
        data.mkdir()
        (data / "episode_000000.parquet").write_bytes(b"PAR1")
        assert classify_staged_root(root) == "empty"


def test_non_v2_info_json_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_lerobot_root(root, version="v3.0")
        assert classify_staged_root(root) == "empty"


def test_v2_info_without_parquet_lists_from_total_episodes():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_lerobot_root(root, parquet=False, total_episodes=1, video_path=None)
        assert classify_staged_root(root) == "lerobot"


def test_v2_info_zero_episodes_no_parquet_is_empty():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_lerobot_root(root, parquet=False, total_episodes=0)
        assert classify_staged_root(root) == "empty"


def test_missing_path_is_empty():
    assert classify_staged_root(Path("/tmp/does-not-exist-lerobot-detect")) == "empty"


def _run_standalone() -> int:
    tests = [
        test_yam_episode_is_yam_hdf5,
        test_lerobot_without_videos_is_lerobot,
        test_lerobot_nested_zip_layout_is_lerobot,
        test_yam_and_lerobot_together_is_mixed,
        test_empty_dir_is_empty,
        test_images_only_is_empty,
        test_orphan_parquet_without_meta_is_empty,
        test_non_v2_info_json_is_empty,
        test_v2_info_without_parquet_lists_from_total_episodes,
        test_v2_info_zero_episodes_no_parquet_is_empty,
        test_missing_path_is_empty,
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
