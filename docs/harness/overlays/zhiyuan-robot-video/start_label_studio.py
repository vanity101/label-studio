#!/usr/bin/env python3
"""Start the Zhiyuan Label Studio container and open the web UI.

Default: image zhiyuan-label-studio:ux, container zhiyuan-ls, port 8080.
Does not use root docker-compose (that file builds the full stack).
Does not rebuild the image unless --build is passed.

  python3 docs/harness/overlays/zhiyuan-robot-video/start_label_studio.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

OVERLAY_DIR = Path(__file__).resolve().parent
ROOT = OVERLAY_DIR.parents[3]
DOCKERFILE = OVERLAY_DIR / "Dockerfile"

DEFAULT_IMAGE = "zhiyuan-label-studio:ux"
DEFAULT_CONTAINER = "zhiyuan-ls"
DEFAULT_PORT = 8080
DEFAULT_URL = "http://127.0.0.1:8080/"


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["docker", *args], check=check)


def _default_data_dir() -> Path:
    env = os.environ.get("LABEL_STUDIO_DATA", "").strip()
    if env:
        return Path(env).expanduser()
    home_data = Path.home() / "Public" / "mydata"
    if home_data.is_dir():
        return home_data
    return ROOT / "mydata"


def ensure_docker(timeout_s: int = 90) -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("未找到 docker 命令。请先安装 Docker Desktop 或 Colima。")
    probe = _docker("info", check=False)
    if probe.returncode == 0:
        return
    if sys.platform == "darwin":
        app = Path("/Applications/Docker.app")
        if app.exists():
            print("正在启动 Docker Desktop…")
            _run(["open", "-a", "Docker"], check=False)
        elif shutil.which("colima"):
            print("正在启动 Colima…")
            _run(["colima", "start"], check=False)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        probe = _docker("info", check=False)
        if probe.returncode == 0:
            return
        time.sleep(2)
    detail = (probe.stderr or probe.stdout or "").strip()
    raise RuntimeError(f"Docker 引擎未就绪: {detail or 'docker info 失败'}")


def image_exists(image: str) -> bool:
    result = _docker("image", "inspect", image, check=False)
    return result.returncode == 0


def container_status(name: str) -> str | None:
    result = _docker(
        "inspect",
        "-f",
        "{{.State.Status}}",
        name,
        check=False,
    )
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def ensure_image(image: str, build: bool) -> None:
    if image_exists(image):
        return
    if not build:
        raise RuntimeError(
            f"镜像 {image} 不存在。先在仓库根目录构建，或加 --build：\n"
            f"  docker build -f {DOCKERFILE.relative_to(ROOT)} -t {image} ."
        )
    print(f"正在构建 {image}（首次会较久）…")
    build_cmd = [
        "docker",
        "build",
        "-f",
        str(DOCKERFILE),
        "-t",
        image,
        str(ROOT),
    ]
    proc = subprocess.run(build_cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError("docker build 失败")


def ensure_container(name: str, image: str, port: int, data_dir: Path, recreate: bool) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    status = container_status(name)
    if recreate and status is not None:
        print(f"正在重建容器 {name}…")
        _docker("rm", "-f", name, check=False)
        status = None
    if status == "running":
        print(f"容器 {name} 已在运行。")
        return
    if status is not None:
        print(f"正在启动已有容器 {name}…")
        started = _docker("start", name, check=False)
        if started.returncode == 0:
            return
        print(f"docker start 失败，改为新建容器: {(started.stderr or '').strip()}")
        _docker("rm", "-f", name, check=False)
    print(f"正在创建容器 {name}（数据目录 {data_dir}）…")
    _docker(
        "run",
        "-d",
        "--name",
        name,
        "-p",
        f"{port}:8080",
        "-v",
        f"{data_dir}:/label-studio/data",
        image,
    )


def wait_http(url: str, timeout_s: int = 90) -> None:
    print(f"等待 {url} 就绪…")
    deadline = time.time() + timeout_s
    last_error = ""
    while time.time() < deadline:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status in (200, 302, 301, 303, 307, 308):
                    print("Label Studio 已就绪。")
                    return
        except urllib.error.HTTPError as exc:
            if exc.code in (200, 302, 301, 303, 307, 308):
                print("Label Studio 已就绪。")
                return
            last_error = f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            last_error = str(exc.reason if getattr(exc, "reason", None) else exc)
        time.sleep(1)
    raise RuntimeError(f"等待超时，页面未就绪: {last_error or url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动智源自建 Label Studio 容器并打开网页")
    parser.add_argument("--image", default=os.environ.get("LABEL_STUDIO_IMAGE", DEFAULT_IMAGE))
    parser.add_argument("--name", default=os.environ.get("LABEL_STUDIO_CONTAINER", DEFAULT_CONTAINER))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LABEL_STUDIO_PORT", DEFAULT_PORT)))
    parser.add_argument("--data", type=Path, default=_default_data_dir())
    parser.add_argument("--url", default=os.environ.get("LABEL_STUDIO_URL", DEFAULT_URL))
    parser.add_argument("--build", action="store_true", help="镜像不存在时在本仓库构建")
    parser.add_argument("--recreate", action="store_true", help="删掉已有容器再用当前镜像新建")
    parser.add_argument("--no-open", action="store_true", help="只启动，不打开浏览器")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ensure_docker()
        ensure_image(args.image, build=args.build)
        ensure_container(args.name, args.image, args.port, args.data, recreate=args.recreate)
        wait_http(args.url)
    except RuntimeError as exc:
        print(f"ENV_FAIL: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        print(f"ENV_FAIL: docker 命令失败: {detail}", file=sys.stderr)
        return 2
    if not args.no_open:
        webbrowser.open(args.url)
        print(f"已打开 {args.url}")
    else:
        print(args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
