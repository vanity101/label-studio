"""Eval for Zhiyuan robot-video UX runtime serving. Contract: robot-video-ux-runtime.md"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVALS = Path(__file__).resolve().parent
OVERLAY = ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video"
DOCKERFILE = OVERLAY / "Dockerfile"
BASE_PATCH = OVERLAY / "patches" / "base.html"
LIVE = os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8080").rstrip("/")


def _reexec_venv_if_playwright_missing() -> None:
    try:
        import playwright  # noqa: F401
        return
    except ImportError:
        pass
    venv_python = ROOT / ".venv" / "bin" / "python"
    public_venv = Path("/Users/vanity/Public/label-studio/.venv/bin/python")
    for candidate in (venv_python, public_venv):
        if candidate.is_file() and Path(sys.executable).resolve() != candidate.resolve():
            os.execv(str(candidate), [str(candidate), *sys.argv])


_reexec_venv_if_playwright_missing()
if str(EVALS) not in sys.path:
    sys.path.insert(0, str(EVALS))

from browser_ui import (  # noqa: E402
    verify_click_place,
    verify_create_project_preset_clicks,
    verify_import_lerobot_clicks,
)


def test_dockerfile_is_official_plus_frontend():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "heartexlabs/label-studio" in text
    assert "bun run build" in text
    assert "web/dist" in text


def test_dockerfile_does_not_alias_vite_onto_webpack_main():
    text = DOCKERFILE.read_text(encoding="utf-8")
    runtime_stage = text.split("FROM heartexlabs/label-studio", 1)[-1]
    assert not re.search(r"cp\s+[^\n]*main-\*\.js[^\n]*\bmain\.js\b", runtime_stage)
    assert "patches/base.html" in text
    assert "core/static_build/js/manifest.json" in text


def test_overlay_html_loads_vite_as_module():
    html = BASE_PATCH.read_text(encoding="utf-8")
    assert 'type="module"' in html
    assert "manifest_asset" in html
    assert "runtime.js" not in html
    assert "/react-app/vendor.js" not in html
    assert "/react-app/main.js?v=" not in html


def test_live_homepage_is_not_blank():
    with urllib.request.urlopen(LIVE + "/", timeout=10) as response:
        body = response.read().decode("utf-8", "replace")
        status = response.status
    assert status == 200
    assert "Label Studio" in body
    assert "Log in" in body or "Projects" in body or "app-wrapper" in body
    assert len(body) > 2000


def test_live_app_js_is_vite_with_click_to_span():
    manifest = None
    for path in (
        "/react-app/static/js/manifest.json",
        "/static/js/manifest.json",
    ):
        try:
            with urllib.request.urlopen(LIVE + path, timeout=10) as response:
                if response.status == 200:
                    manifest = json.loads(response.read().decode("utf-8"))
                    break
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            continue
    assert isinstance(manifest, dict), "侍出 manifest.json 不可读"
    entry = manifest.get("main.js", "")
    assert entry.startswith("/react-app/"), entry
    assert Path(entry).name != "main.js"
    with urllib.request.urlopen(LIVE + entry, timeout=15) as response:
        js = response.read().decode("utf-8", "replace")
    assert "webpackChunk" not in js[:120]
    chunks = re.findall(r'"(src-[A-Za-z0-9_-]+\.js)"', js)
    blob = js
    for name in chunks:
        with urllib.request.urlopen(LIVE + "/react-app/" + name, timeout=15) as response:
            blob += response.read().decode("utf-8", "replace")
    assert "handleLabelClick" in blob
    assert "nextClickSpan" in blob or "TimelineLabelsClickToSpan" in blob


def test_live_browser_click_place_creates_span():
    """Must open Chromium, log in, and click place_object. curl / JS grep is not this test."""
    verify_click_place()


def test_live_browser_create_project_preset_clicks():
    """Must click Labeling Setup → Browse Templates → Custom/Code, then Settings isolation."""
    verify_create_project_preset_clicks()


def test_live_browser_import_lerobot_clicks():
    """Must click Data Import upload/dropzone and see LeRobot copy plus mix/orphan errors."""
    verify_import_lerobot_clicks()


def _run_standalone() -> int:
    tests = [
        test_dockerfile_is_official_plus_frontend,
        test_dockerfile_does_not_alias_vite_onto_webpack_main,
        test_overlay_html_loads_vite_as_module,
        test_live_homepage_is_not_blank,
        test_live_app_js_is_vite_with_click_to_span,
        test_live_browser_click_place_creates_span,
        test_live_browser_create_project_preset_clicks,
        test_live_browser_import_lerobot_clicks,
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
