#!/usr/bin/env python3
"""Start Zhiyuan Label Studio (默认 Docker :8080) and open the web UI.

Default: 镜像 zhiyuan-label-studio:ux，容器 zhiyuan-ls，http://127.0.0.1:8080/
（镜像内嵌 Debian Python+TF，可解 RLDS）。本机源码加 --local。

  python3 docs/harness/overlays/zhiyuan-robot-video/start_label_studio.py
  python3 docs/harness/overlays/zhiyuan-robot-video/start_label_studio.py --build --recreate
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
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
# 容器进程仍听 8080；主机端口由 --port 映射。
CONTAINER_PORT = 8080

DEFAULT_UPLOAD_BYTES = str(8 * 1024 * 1024 * 1024)


def rlds_env() -> dict[str, str]:
    return {
        "DATA_UPLOAD_MAX_MEMORY_SIZE": os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", DEFAULT_UPLOAD_BYTES),
        "NO_GCE_CHECK": os.environ.get("NO_GCE_CHECK", "true"),
        "GCE_METADATA_TIMEOUT": os.environ.get("GCE_METADATA_TIMEOUT", "0"),
        "TF_CPP_MIN_LOG_LEVEL": os.environ.get("TF_CPP_MIN_LOG_LEVEL", "2"),
        "RLDS_IMPORT_MAX_EPISODES": os.environ.get("RLDS_IMPORT_MAX_EPISODES", "16"),
        "ROBOT_IMPORT_MAX_EPISODES": os.environ.get("ROBOT_IMPORT_MAX_EPISODES", "16"),
        "ROBOT_IMPORT_PYTHON": os.environ.get("ROBOT_IMPORT_PYTHON", os.environ.get("RLDS_PYTHON", "")),
    }


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


def container_has_rlds(name: str) -> bool:
    decode = _docker(
        "exec",
        name,
        "test",
        "-f",
        "/label-studio/label_studio/robot_import/worker.py",
        check=False,
    )
    worker = _docker(
        "exec",
        name,
        "test",
        "-x",
        "/opt/rlds/bin/python",
        check=False,
    )
    return decode.returncode == 0 and worker.returncode == 0


def warn_if_missing_rlds(name: str) -> None:
    if container_has_rlds(name):
        return
    print(
        "警告: 容器内没有 HDF5 解码器（robot_import 或 /opt/rlds/bin/python）。"
        "请加 --docker --build --recreate 用当前 Dockerfile 重建。",
        file=sys.stderr,
    )


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
    exists = image_exists(image)
    if exists and not build:
        return
    if not exists and not build:
        raise RuntimeError(
            f"镜像 {image} 不存在。先在仓库根目录构建，或加 --build：\n"
            f"  docker build -f {DOCKERFILE.relative_to(ROOT)} -t {image} ."
        )
    print(f"正在构建 {image}（apk/清华、bun/npmmirror、pip/清华；内嵌 Debian Python+TF）…")
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
        warn_if_missing_rlds(name)
        return
    if status is not None:
        print(f"正在启动已有容器 {name}…")
        started = _docker("start", name, check=False)
        if started.returncode == 0:
            warn_if_missing_rlds(name)
            return
        print(f"docker start 失败，改为新建容器: {(started.stderr or '').strip()}")
        _docker("rm", "-f", name, check=False)
    print(f"正在创建容器 {name}（数据目录 {data_dir}）…")
    run_args = [
        "run",
        "-d",
        "--name",
        name,
        "-p",
        f"{port}:{CONTAINER_PORT}",
        "-v",
        f"{data_dir}:/label-studio/data",
    ]
    for key, value in rlds_env().items():
        run_args.extend(["-e", f"{key}={value}"])
    run_args.append(image)
    _docker(*run_args)


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
        except (OSError, TimeoutError) as exc:
            last_error = str(exc.reason) if getattr(exc, "reason", None) else str(exc)
        time.sleep(1)
    raise RuntimeError(f"等待超时，页面未就绪: {last_error or url}")


def _venv_label_studio() -> Path:
    return ROOT / ".venv" / "bin" / "label-studio"


def port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def ensure_local(port: int, data_dir: Path) -> None:
    binary = _venv_label_studio()
    if not binary.is_file():
        raise RuntimeError(
            f"未找到 {binary}。先在仓库根目录：\n"
            "  uv venv .venv --python 3.11\n"
            "  uv pip install --python .venv/bin/python --no-config --no-sources -e . "
            "-i https://pypi.tuna.tsinghua.edu.cn/simple\n"
            "  uv pip install --python .venv/bin/python --no-config --no-sources "
            "-i https://pypi.tuna.tsinghua.edu.cn/simple tensorflow tensorflow-datasets Pillow"
        )
    data_dir.mkdir(parents=True, exist_ok=True)
    if port_listening(port):
        print(f"本机 {port} 已有服务在听，跳过启动。")
        return
    env = os.environ.copy()
    env.update(rlds_env())
    env["LABEL_STUDIO_BASE_DATA_DIR"] = str(data_dir)
    env.setdefault("USERNAME", "rlds-verify@localhost")
    env.setdefault("PASSWORD", "rldsverify123")
    log_path = data_dir / "label-studio-local.log"
    log_file = log_path.open("ab")
    print(f"正在用 .venv 启动 Label Studio（端口 {port}，日志 {log_path}）…")
    subprocess.Popen(
        [
            str(binary),
            "start",
            "--username",
            env["USERNAME"],
            "--password",
            env["PASSWORD"],
            "--port",
            str(port),
            "--internal-host",
            "127.0.0.1",
            "--no-browser",
            "--data-dir",
            str(data_dir),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动智源 Label Studio（默认 Docker :8080）并打开网页")
    parser.add_argument("--image", default=os.environ.get("LABEL_STUDIO_IMAGE", DEFAULT_IMAGE))
    parser.add_argument("--name", default=os.environ.get("LABEL_STUDIO_CONTAINER", DEFAULT_CONTAINER))
    parser.add_argument("--port", type=int, default=int(os.environ.get("LABEL_STUDIO_PORT", DEFAULT_PORT)))
    parser.add_argument("--data", type=Path, default=_default_data_dir())
    parser.add_argument("--url", default=os.environ.get("LABEL_STUDIO_URL", DEFAULT_URL))
    parser.add_argument("--build", action="store_true", help="用当前 Dockerfile 重建镜像（即使已存在）")
    parser.add_argument("--recreate", action="store_true", help="删掉已有容器再用当前镜像新建")
    parser.add_argument(
        "--docker",
        action="store_true",
        help="启动 Docker 容器（默认；镜像内嵌 TF，8080 可解 RLDS）",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="用仓库 .venv 源码启动（不走 Docker）",
    )
    parser.add_argument("--no-open", action="store_true", help="只启动，不打开浏览器")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.url in {DEFAULT_URL, "http://127.0.0.1:8081/"} and args.port != DEFAULT_PORT:
        args.url = f"http://127.0.0.1:{args.port}/"
    elif args.url == "http://127.0.0.1:8081/" and args.port == DEFAULT_PORT:
        args.url = DEFAULT_URL
    use_docker = not args.local
    try:
        if use_docker:
            ensure_docker()
            ensure_image(args.image, build=args.build)
            ensure_container(args.name, args.image, args.port, args.data, recreate=args.recreate)
        else:
            ensure_local(args.port, args.data)
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
