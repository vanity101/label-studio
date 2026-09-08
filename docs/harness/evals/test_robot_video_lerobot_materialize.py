"""Eval for LeRobot preview materialize (S1-T2). Spec DAT-002, FR-006, FR-007, NFR-005, NFR-006."""

from __future__ import annotations

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
from robot_import.lerobot_format import list_episodes  # noqa: E402
from robot_import.lerobot_materialize import (  # noqa: E402
    HIGH_CAM_COLUMN,
    file_sha256,
    materialize_episode,
)


def _require_materialize_deps() -> None:
    try:
        import pyarrow  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise AssertionError(
            "LeRobot 物化测试需要 pyarrow / Pillow。"
            "请安装: pip install pyarrow Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple "
            "--trusted-host pypi.tuna.tsinghua.edu.cn"
        ) from exc
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise AssertionError("LeRobot 物化测试需要系统 ffmpeg / ffprobe")


def _jpeg_bytes(color: tuple[int, int, int], size: tuple[int, int] = (192, 320)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _write_high_cam_parquet(path: Path, frames: int = 3, *, extra_cam: bool = False) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    struct_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    colors = [(220, 30, 30), (30, 180, 40), (40, 60, 210), (200, 200, 40)]
    rows = [
        {"bytes": _jpeg_bytes(colors[index % len(colors)]), "path": f"frame_{index:03d}.jpg"}
        for index in range(frames)
    ]
    fields = {HIGH_CAM_COLUMN: pa.array(rows, type=struct_type)}
    if extra_cam:
        fields["observation.images.l_cam"] = pa.array(rows, type=struct_type)
        fields["action"] = pa.array([[0.0] * 7] * frames, type=pa.list_(pa.float32()))
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(fields), path)


def _write_l_cam_only_parquet(path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    struct_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    rows = [{"bytes": _jpeg_bytes((10, 10, 10)), "path": "x.jpg"}]
    table = pa.table({"observation.images.l_cam": pa.array(rows, type=struct_type)})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _parquet_info(*, video_path=None) -> dict:
    return {
        "codebase_version": "v2.1",
        "fps": 10,
        "total_episodes": 1,
        "chunks_size": 1000,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": video_path,
        "features": {
            "observation.images.high_cam": {"dtype": "image", "shape": [192, 320, 3]},
            "action": {"dtype": "float32", "shape": [7]},
        },
    }


def _write_parquet_dataset(root: Path, *, with_images_dir: bool = False) -> Path:
    meta = root / "meta"
    meta.mkdir(parents=True)
    (meta / "info.json").write_text(json.dumps(_parquet_info()), encoding="utf-8")
    (meta / "episodes.jsonl").write_text(
        json.dumps({"episode_index": 0, "episode_id": "episode_000000", "length": 3}) + "\n",
        encoding="utf-8",
    )
    parquet = root / "data" / "chunk-000" / "episode_000000.parquet"
    _write_high_cam_parquet(parquet, frames=3, extra_cam=True)
    if with_images_dir:
        junk = root / "images" / "cam" / "000.jpg"
        junk.parent.mkdir(parents=True)
        junk.write_bytes(_jpeg_bytes((1, 2, 3), size=(16, 16)))
    return root


def test_copy_existing_mp4_without_reencode():
    _require_materialize_deps()
    from robot_import.lerobot_materialize import count_mp4_frames

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
        before = file_sha256(source)
        item = list_episodes(root)[0]
        assert item["video_path"] is not None
        preview_root = Path(tmp) / "media"
        result = materialize_episode(item, preview_root, dataset_root=root)
        dest = Path(result["preview_path"])
        assert dest.is_file()
        assert dest.name == "preview.mp4"
        assert dest.parent.name == "episode_000000"
        assert result["copied"] is True
        assert file_sha256(dest) == before
        assert file_sha256(source) == before
        assert count_mp4_frames(dest) == count_mp4_frames(source)


def test_parquet_high_cam_without_videos():
    _require_materialize_deps()
    from robot_import.lerobot_materialize import count_mp4_frames

    with tempfile.TemporaryDirectory() as tmp:
        root = _write_parquet_dataset(Path(tmp) / "ds", with_images_dir=True)
        images_before = file_sha256(root / "images" / "cam" / "000.jpg")
        parquet_before = file_sha256(root / "data" / "chunk-000" / "episode_000000.parquet")
        episodes = list_episodes(root)
        assert episodes[0]["video_path"] is None
        preview_root = Path(tmp) / "media"
        result = materialize_episode(episodes[0], preview_root, dataset_root=root)
        dest = Path(result["preview_path"])
        assert dest.is_file()
        assert result["copied"] is False
        assert result["num_frames"] == 3
        assert count_mp4_frames(dest) == 3
        assert result["fps"] == 10
        assert file_sha256(root / "data" / "chunk-000" / "episode_000000.parquet") == parquet_before
        assert file_sha256(root / "images" / "cam" / "000.jpg") == images_before
        assert not (preview_root / "images").exists()


def test_reject_when_no_mp4_and_no_high_cam():
    _require_materialize_deps()
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
        (root / "images" / "frame.jpg").parent.mkdir(parents=True)
        (root / "images" / "frame.jpg").write_bytes(_jpeg_bytes((9, 9, 9)))
        item = list_episodes(root)[0]
        try:
            materialize_episode(item, Path(tmp) / "media", dataset_root=root)
        except RobotImportError as exc:
            text = str(exc)
            assert "high_cam" in text
            assert "l_cam" not in text.lower() or "不得" in text or "没有" in text
        else:
            raise AssertionError("expected RobotImportError when neither mp4 nor high_cam exists")


def test_mp4_wins_over_parquet_and_does_not_reencode():
    _require_materialize_deps()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ds"
        shutil.copytree(FIXTURE, root)
        parquet = root / "data" / "chunk-000" / "episode_000000.parquet"
        _write_high_cam_parquet(parquet, frames=3)
        source = (
            root
            / "videos"
            / "chunk-000"
            / "observation.images.cam_high"
            / "episode_000000.mp4"
        )
        source_hash = file_sha256(source)
        item = list_episodes(root)[0]
        result = materialize_episode(item, Path(tmp) / "media", dataset_root=root)
        assert result["copied"] is True
        assert file_sha256(Path(result["preview_path"])) == source_hash


def test_source_does_not_import_pandas_or_read_full_table():
    text = (LS / "robot_import" / "lerobot_materialize.py").read_text(encoding="utf-8")
    assert "pandas" not in text
    assert "read_table" not in text
    assert "iter_batches" in text
    assert "columns=[HIGH_CAM_COLUMN]" in text
    assert HIGH_CAM_COLUMN in text
    assert "images/" in text and "不读" in text


def _run_standalone() -> int:
    tests = [
        test_copy_existing_mp4_without_reencode,
        test_parquet_high_cam_without_videos,
        test_reject_when_no_mp4_and_no_high_cam,
        test_mp4_wins_over_parquet_and_does_not_reencode,
        test_source_does_not_import_pandas_or_read_full_table,
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
