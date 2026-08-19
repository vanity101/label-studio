#!/usr/bin/env python3
"""Optional: create a project from the single-view overlay via Label Studio API."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

OVERLAY_DIR = Path(__file__).resolve().parent
CONFIG = (OVERLAY_DIR / "configs" / "single-view.xml").read_text(encoding="utf-8")
TASKS = json.loads((OVERLAY_DIR / "examples" / "tasks-single-view.json").read_text(encoding="utf-8"))


def _request(url: str, api_key: str, method: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 Label Studio（环境问题，不改 Django）: {exc}") from exc
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"API 返回不是 JSON（环境问题，不改 Django）: {body[:200]!r}") from exc


def main() -> int:
    base = os.environ.get("LABEL_STUDIO_URL", "").rstrip("/")
    api_key = os.environ.get("LABEL_STUDIO_API_KEY", "")
    if not base or not api_key:
        print(
            "SKIP: 未设置 LABEL_STUDIO_URL / LABEL_STUDIO_API_KEY。"
            "按 README 用 Docker 手工建项目即可。",
            file=sys.stderr,
        )
        return 0
    project = _request(
        f"{base}/api/projects",
        api_key,
        "POST",
        {"title": "Zhiyuan robot video (single-view)", "label_config": CONFIG},
    )
    project_id = project.get("id")
    if not project_id:
        raise RuntimeError(f"创建项目返回缺少 id: {project!r}")
    imported = _request(
        f"{base}/api/projects/{project_id}/import",
        api_key,
        "POST",
        TASKS,
    )
    print(f"created project_id={project_id}")
    print(json.dumps({"project": project_id, "import": imported}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ENV_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
