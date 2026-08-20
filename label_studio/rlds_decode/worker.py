"""独立进程入口：Django 请求线程不要直接跑 TensorFlow。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("NO_GCE_CHECK", "true")
    os.environ.setdefault("GCE_METADATA_TIMEOUT", "0")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

    parser = argparse.ArgumentParser()
    parser.add_argument("bronze")
    parser.add_argument("preview_root")
    parser.add_argument("--existing", default="")
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        from rlds_decode.import_batch import decode_bronze_to_tasks

        existing = {item for item in args.existing.split(",") if item}
        result = decode_bronze_to_tasks(
            Path(args.bronze),
            Path(args.preview_root),
            existing_episode_ids=existing,
            max_episodes=args.max_episodes,
            fps=args.fps,
        )
        payload = {
            "ok": True,
            "tasks": result.tasks,
            "skipped_episode_ids": result.skipped_episode_ids,
            "truncated": result.truncated,
            "listed": result.listed,
        }
    except Exception as exc:  # noqa: BLE001
        import traceback

        payload = {"ok": False, "error": str(exc), "trace": traceback.format_exc()}
        Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
        return 1
    Path(args.out).write_text(json.dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
