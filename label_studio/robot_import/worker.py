"""独立进程入口：避免在 Django 请求线程里打开大型 HDF5。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="YAM HDF5 → preview.mp4")
    parser.add_argument("bronze")
    parser.add_argument("preview_root")
    parser.add_argument("--out", required=True)
    parser.add_argument("--existing", default="")
    parser.add_argument("--max-episodes", type=int, default=None)
    args = parser.parse_args()
    existing = {item for item in args.existing.split(",") if item}
    try:
        from robot_import.import_batch import decode_bronze_to_tasks

        result = decode_bronze_to_tasks(
            Path(args.bronze),
            Path(args.preview_root),
            existing_episode_ids=existing,
            max_episodes=args.max_episodes,
        )
        payload = {
            "ok": True,
            "tasks": result.tasks,
            "skipped_episode_ids": result.skipped_episode_ids,
            "truncated": result.truncated,
            "listed": result.listed,
        }
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": str(exc)}
    Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
