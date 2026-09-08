"""Eval for LeRobot decode_lerobot_to_tasks (S1-T4). Spec FR-003…FR-009, DAT-002."""

from __future__ import annotations

import hashlib
import io
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
from robot_import.import_batch import (  # noqa: E402
    decode_lerobot_to_tasks,
    decode_lerobot_to_tasks_isolated,
    skip_existing,
)
from robot_import.lerobot_materialize import HIGH_CAM_COLUMN  # noqa: E402


def _require_batch_deps() -> None:
    try:
        import pyarrow  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as cop:
        raise AssertionError(
            "LeRobot batch 测试需要 pyarrow / Pillow。"
            "请安装: pip install pyarrow Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple "
            "--trusted-host pypi.tuna.tsinghua.edu.cn"
        ) from cop
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AssertionError("LeRobot batch 测试需要系统 ffmpeg / ffprobe")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jpeg_bytes(color: tuple[int, int, int], size: tuple[int, int] = (192, 320)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _write_high_cam_parquet(path: Path, frames: int = 3) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    struct_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    colors = [(220, 30, 30), (30, 180, 40), (40, 60, 210)]
    rows = [
        {"bytes": _jpeg_bytes(colors[index % len(colors)]), "path": f"frame_{index:03d}.jpg"}
        for index in range(frames)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({HIGH_CAM_COLUMN: pa.array(rows, type=struct_type)}), path)


def _write_parquet_dataset(root: Path, *, episodes: int = 2, frames: int = 3) -> Path:
    meta = root / "meta"
    meta.mkdir(parents=True)
    info = {
        "codebase_version": "v2.1",
        "fps": 10,
        "total_episodes": episodes,
        "chunks_size": 1000,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": None,
        "features": {
            "observation.images.high_cam": {"dtype": "image", "shape": [192, 320, 3]},
            "action": {"dtype": "float32", "shape": [7]},
        },
    }
    (meta / "info.json").write_text(json.dumps(info), encoding="utf-8")
    lines = [
        json.dumps({"episode_index": index, "episode_id": f"episode_{index:06d}", "length": frames})
        for index in range(episodes)
    ]
    (meta / "episodes.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for index in range(episodes):
        _write_high_cam_parquet(
            root / "data" / "chunk-000" / f"episode_{index:06d}.parquet",
            frames=frames,
        )
    return root


def test_skip_existing_reused():
    pending, skipped = skip_existing(["episode_000000", "episode_000001"], {"episode_000000"})
    assert pending == ["episode_000001"]
    assert skipped == ["episode_000000"]


def test_mp4_batch_source_type_and_skip():
    _require_batch_deps()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ds"
        shutil.copytree(FIXTURE, root)
        source = (
            root
            / "videos"
            / "chunk-000"
            / "observation.images.cam_high"
            / "episode_000000.mp4"
        )
        before = _file_sha256(source)
        preview_root = Path(tmp) / "media"
        first = decode_lerobot_to_tasks(root, preview_root)
        assert first.listed == 1
        assert len(first.tasks) == 1
        data = first.tasks[0]["data"]
        assert data["source_type"] == "lerobot"
        assert data["episode_id"] == "episode_000000"
        assert data["camera"] == "cam_high"
        assert str(data["video"]).endswith("preview.mp4")
        assert Path(data["video"]).is_file()
        assert _file_sha256(source) == before
        assert _file_sha256(Path(data["video"])) == before
        second = decode_lerobot_to_tasks(
            root,
            preview_root,
            existing_episode_ids={"episode_000000"},
        )
        assert second.tasks == []
        assert second.skipped_episode_ids == ["episode_000000"]
        assert second.listed == 1


def test_parquet_high_cam_without_videos():
    _require_batch_deps()
    from robot_import.lerobot_materialize import count_mp4_frames

    with tempfile.TemporaryDirectory() as tmp:
        root = _write_parquet_dataset(Path(tmp) / "ds", episodes=1, frames=3)
        parquet = root / "data" / "chunk-000" / "episode_000000.parquet"
        before = _file_sha256(parquet)
        assert not (root / "videos").exists()
        preview_root = Path(tmp) / "media"
        result = decode_lerobot_to_tasks(root, preview_root)
        assert result.listed == 1
        assert len(result.tasks) == 1
        data = result.tasks[0]["data"]
        assert data["source_type"] == "lerobot"
        assert data["episode_id"] == "episode_000000"
        assert data["camera"] == "high_cam"
        assert data["fps"] == 10
        assert data["num_frames"] == 3
        assert count_mp4_frames(Path(data["video"])) == 3
        assert _file_sha256(parquet) == before


def test_max_episodes_truncates():
    _require_batch_deps()
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_parquet_dataset(Path(tmp) / "ds", episodes=2, frames=2)
        result = decode_lerobot_to_tasks(root, Path(tmp) / "media", max_episodes=1)
        assert result.listed == 2
        assert result.truncated is True
        assert [task["data"]["episode_id"] for task in result.tasks] == ["episode_000000"]


def test_isolated_worker_parquet_batch():
    _require_batch_deps()
    with tempfile.TemporaryDirectory() as tmp:
        root = _write_parquet_dataset(Path(tmp) / "ds", episodes=1, frames=2)
        result = decode_lerobot_to_tasks_isolated(root, Path(tmp) / "media")
        assert result.listed == 1
        assert len(result.tasks) == 1
        assert result.tasks[0]["data"]["source_type"] == "lerobot"
        assert Path(result.tasks[0]["data"]["video"]).is_file()


def _write_l_cam_only_parquet(path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    struct_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    rows = [{"bytes": _jpeg_bytes((10, 10, 10)), "path": "x.jpg"}]
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table({"observation.images.l_cam": pa.array(rows, type=struct_type)}), path)


def test_reject_no_preview_source():
    _require_batch_deps()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ds"
        meta = root / "meta"
        meta.mkdir(parents=True)
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
        _write_l_cam_only_parquet(root / "data" / "chunk-000" / "episode_000000.parquet")
        try:
            decode_lerobot_to_tasks(root, Path(tmp) / "media")
        except RobotImportError as cop:
            text = str(cop)
            assert "high_cam" in text
        else:
            raise AssertionError("expected RobotImportError when neither mp4 nor high_cam exists")


def test_does_not_rewrite_hdf5_eval_or_t1_t3_files():
    hdf5_eval = (EVALS / "test_robot_video_hdf5_import.py").read_text(encoding="utf-8")
    assert "decode_lerobot_to_tasks" not in hdf5_eval
    batch = (LS / "robot_import" / "import_batch.py").read_text(encoding="utf-8")
    assert "decode_lerobot_to_tasks" in batch
    assert "source_type" in batch and '"lerobot"' in batch
    assert "skip_existing" in batch
    assert "import_max_episodes" in batch
    worker = (LS / "robot_import" / "worker.py").read_text(encoding="utf-8")
    assert "--source" in worker
    assert "decode_lerobot_to_tasks" in worker


def _run_standalone() -> int:
    tests = [
        test_skip_existing_reused,
        test_mp4_batch_source_type_and_skip,
        test_parquet_high_cam_without_videos,
        test_max_episodes_truncates,
        test_isolated_worker_parquet_batch,
        test_reject_no_preview_source,
        test_does_not_rewrite_hdf5_eval_or_t1_t3_files,
    ]
    failed = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as cop:  # noqa: BLE001
            failed.append(test.__name__)
            print(f"FAIL {test.__name__}: {cop}")
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
