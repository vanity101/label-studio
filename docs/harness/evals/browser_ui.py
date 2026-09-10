"""Live-browser verification for Zhiyuan overlay. Curl is not enough."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

OVERLAY = Path(__file__).resolve().parents[1] / "overlays" / "zhiyuan-robot-video"
SINGLE_VIEW = OVERLAY / "configs" / "single-view.xml"
TASKS = json.loads((OVERLAY / "examples" / "tasks-single-view.json").read_text(encoding="utf-8"))

LIVE = os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8080").rstrip("/")
EVAL_EMAIL = os.environ.get("LABEL_STUDIO_EVAL_EMAIL", "").strip()
EVAL_PASSWORD = os.environ.get("LABEL_STUDIO_EVAL_PASSWORD", "").strip()
DEFAULT_PASSWORD = "RuntimeEval!12345"

PIP_MIRROR = (
    "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn playwright && "
    "PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright python -m playwright install chromium"
)

CLICK_PLACE_JS = """
() => {
  const Htx = window.Htx;
  if (!Htx || !Htx.annotationStore) return { ok: false, error: "no window.Htx" };
  const as = Htx.annotationStore;
  if (typeof as.createAnnotation === "function") {
    as.createAnnotation();
  }
  const selected = as.selected;
  if (!selected) return { ok: false, error: "no selected annotation" };
  const names = selected.names || as.names;
  const video = names && names.get && names.get("video");
  if (!video) return { ok: false, error: "no video tag" };
  if (typeof video.setOnlyFrame === "function") video.setOnlyFrame(30);
  else if (typeof video.setFrame === "function") video.setFrame(30);
  const labels = names.get && names.get("videoLabels");
  const place = labels && (labels.children || []).find((c) => c.value === "Place");
  if (labels && place && typeof labels.handleLabelClick === "function") {
    labels.handleLabelClick(place);
  } else {
    const el = [...document.querySelectorAll("button, span, div")].find(
      (node) => node.textContent && node.textContent.trim() === "Place" && node.offsetParent
    );
    if (!el) return { ok: false, error: "Place control not found" };
    el.click();
  }
  const regions = (selected.regionStore && selected.regionStore.regions) || [];
  const dumped = regions.map((r) => ({
    type: r.type,
    start: r.ranges && r.ranges[0] && r.ranges[0].start,
    end: r.ranges && r.ranges[0] && r.ranges[0].end,
    placeSelected: !!(place && place.selected),
  }));
  return {
    ok: true,
    frame: video.currentFrame != null ? video.currentFrame : video.frame,
    placeSelected: !!(place && place.selected),
    regions: dumped,
    moduleScripts: [...document.querySelectorAll('script[type="module"]')].map((s) => s.src),
    hasAppWrapper: !!document.querySelector(".app-wrapper"),
  };
}
"""


def playwright_missing_message(exc: BaseException) -> str:
    return (
        f"缺 Playwright 或 Chromium（{exc}）。禁止 skip。安装：{PIP_MIRROR}"
    )


def require_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise AssertionError(playwright_missing_message(exc)) from exc
    return sync_playwright


def _fill_auth(page, email: str, password: str) -> None:
    page.locator("input[name=email], #email").first.fill(email)
    page.locator("input[name=password], #password").first.fill(password)


def _logged_in(page) -> bool:
    if page.locator(".app-wrapper").count() > 0:
        return True
    url = page.url or ""
    if "/user/login" in url or "/user/signup" in url:
        return False
    return "Log in" not in page.content()[:4000]


def ensure_logged_in(page) -> None:
    page.goto(LIVE + "/", wait_until="domcontentloaded", timeout=30000)
    if _logged_in(page):
        return

    password = EVAL_PASSWORD or DEFAULT_PASSWORD
    if EVAL_EMAIL:
        page.goto(LIVE + "/user/login/", wait_until="domcontentloaded", timeout=30000)
        _fill_auth(page, EVAL_EMAIL, password)
        page.locator("button[type=submit], button:has-text('Log in')").first.click()
        page.wait_for_timeout(1500)
        if _logged_in(page):
            return

    email = EVAL_EMAIL or f"eval-{int(time.time())}@example.com"
    page.goto(LIVE + "/user/signup/", wait_until="domcontentloaded", timeout=30000)
    body = page.content()
    if "Sign Up" not in body and "Create Account" not in body:
        raise AssertionError(
            "无法注册且未登录。设置 LABEL_STUDIO_EVAL_EMAIL / LABEL_STUDIO_EVAL_PASSWORD "
            "为已有账号后再跑。"
        )
    _fill_auth(page, email, password)
    how = page.locator("select[name=how_find_us], #how_find_us")
    if how.count():
        options = how.locator("option:not([disabled])")
        if options.count() > 1:
            how.select_option(index=1)
    page.locator("button[type=submit], button:has-text('Create Account')").first.click()
    page.wait_for_timeout(2000)
    if _logged_in(page):
        return
    page.goto(LIVE + "/user/login/", wait_until="domcontentloaded", timeout=30000)
    _fill_auth(page, email, password)
    page.locator("button[type=submit], button:has-text('Log in')").first.click()
    page.wait_for_timeout(2000)
    if not _logged_in(page):
        raise AssertionError(
            "登录失败。设置 LABEL_STUDIO_EVAL_EMAIL / LABEL_STUDIO_EVAL_PASSWORD 后重跑。"
        )


def _api(page, method: str, path: str, payload=None):
    # 走页面 fetch + session cookie。本实例组织关掉了 legacy Token，禁止带 Authorization。
    result = page.evaluate(
        """async ({ method, path, payload }) => {
          const csrf = document.cookie.split("; ").find((x) => x.startsWith("csrftoken="));
          const headers = { "Content-Type": "application/json" };
          if (csrf) headers["X-CSRFToken"] = csrf.split("=")[1];
          const opts = { method, credentials: "same-origin", headers };
          if (payload !== null && method !== "GET") opts.body = JSON.stringify(payload);
          const resp = await fetch(path, opts);
          const text = await resp.text();
          return { status: resp.status, text };
        }""",
        {"method": method, "path": path, "payload": payload},
    )
    if result["status"] >= 400:
        raise AssertionError(
            f"API {method} {path} HTTP {result['status']}: {result['text'][:400]}"
        )
    text = result["text"]
    return json.loads(text) if text else {}


def seed_single_view_task(page) -> tuple[int, int]:
    config = SINGLE_VIEW.read_text(encoding="utf-8")
    projects = _api(page, "GET", "/api/projects/")
    results = projects if isinstance(projects, list) else projects.get("results") or []
    for project in results:
        pid = project.get("id")
        if not pid:
            continue
        config_xml = project.get("label_config") or ""
        if 'value="Place"' not in config_xml:
            continue
        tasks = _api(page, "GET", f"/api/tasks/?project={pid}")
        task_list = tasks if isinstance(tasks, list) else tasks.get("tasks") or tasks.get("results") or []
        if task_list:
            tid = task_list[0].get("id")
            if tid:
                return int(pid), int(tid)
    created = _api(
        page,
        "POST",
        "/api/projects/",
        {"title": "runtime-eval-click-place", "label_config": config},
    )
    pid = created.get("id")
    if not pid:
        raise AssertionError(f"创建项目失败: {created!r}")
    _api(page, "POST", f"/api/projects/{pid}/import", TASKS)
    tasks = _api(page, "GET", f"/api/tasks/?project={pid}")
    task_list = tasks if isinstance(tasks, list) else tasks.get("tasks") or tasks.get("results") or []
    if not task_list:
        raise AssertionError("导入任务后列表为空")
    return int(pid), int(task_list[0]["id"])


def verify_click_place() -> dict:
    sync_playwright = require_playwright()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                ensure_logged_in(page)
                assert page.locator(".app-wrapper").count() > 0, "登录后没有 .app-wrapper（应用未加载）"
                html = page.content()
                assert "type=\"module\"" in html or page.locator("script[type=module]").count() > 0, (
                    "登录后页面没有 type=module 入口"
                )
                pid, tid = seed_single_view_task(page)
                page.goto(
                    f"{LIVE}/projects/{pid}/data?task={tid}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_function(
                    "() => window.Htx && window.Htx.annotationStore",
                    timeout=60000,
                )
                result = page.evaluate(CLICK_PLACE_JS)
                assert result and result.get("ok"), f"点 Place 脚本失败: {result!r}"
                regions = [r for r in result.get("regions") or [] if r.get("type") == "timelineregion"]
                assert regions, f"点 Place 后没有 timelineregion: {result!r}"
                span = regions[-1]
                start, end = span.get("start"), span.get("end")
                frame = result.get("frame")
                assert start == 1, f"期望 start=1，实际 {start}（{result!r}）"
                assert end == frame, f"期望 end=播放头 {frame}，实际 {end}（{result!r}）"
                assert end != start, f"仍是官方单帧 start=end={start}"
                assert result.get("placeSelected") is False, f"Place 仍保持选中: {result!r}"
                return result
            finally:
                browser.close()
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if "Executable doesn't exist" in str(exc) or name in {"Error"}:
            raise AssertionError(playwright_missing_message(exc)) from exc
        raise AssertionError(f"浏览器核验失败（禁止 skip）: {exc}") from exc
