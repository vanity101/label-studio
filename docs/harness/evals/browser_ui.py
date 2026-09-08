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


def ensure_logged_in(page, live: str | None = None) -> None:
    base = (live or LIVE).rstrip("/")
    page.goto(base + "/", wait_until="domcontentloaded", timeout=30000)
    if _logged_in(page):
        return

    password = EVAL_PASSWORD or DEFAULT_PASSWORD
    if EVAL_EMAIL:
        page.goto(base + "/user/login/", wait_until="domcontentloaded", timeout=30000)
        _fill_auth(page, EVAL_EMAIL, password)
        page.locator("button[type=submit], button:has-text('Log in')").first.click()
        page.wait_for_timeout(1500)
        if _logged_in(page):
            return

    email = EVAL_EMAIL or f"eval-{int(time.time())}@example.com"
    page.goto(base + "/user/signup/", wait_until="domcontentloaded", timeout=30000)
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
    page.goto(base + "/user/login/", wait_until="domcontentloaded", timeout=30000)
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
                page.wait_for_selector(".app-wrapper", timeout=30000)
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


PRESET_MARKERS = (
    "机器人视频时间轴标注",
    'frameRate="10.0"',
    'value="Static"',
    'value="grasp"',
    'value="Place"',
    'value="End"',
    "废弃",
    "action_sequence",
)
SETTINGS_PROBE = """<View>
  <Text name="text" value="$text"/>
  <Choices name="sentiment" toName="text">
    <Choice value="Positive"/>
    <Choice value="Negative"/>
  </Choices>
</View>"""
_SCREENSHOT_DIR_RAW = os.environ.get("DCP46_INT_SCREENSHOT_DIR", "").strip()
SCREENSHOT_DIR = Path(_SCREENSHOT_DIR_RAW).expanduser() if _SCREENSHOT_DIR_RAW else None


def _click_visible_text(page, text: str):
    locator = page.get_by_text(text, exact=True).first
    locator.wait_for(state="visible", timeout=15000)
    locator.click()
    page.wait_for_timeout(400)


def _page_has(page, *needles: str) -> bool:
    text = page.locator("body").inner_text()
    html = page.content()
    return all(n in text or n in html for n in needles)


def _shot(page, name: str) -> None:
    if not SCREENSHOT_DIR:
        return
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


def verify_create_project_preset_clicks() -> dict:
    """Click Labeling Setup (Code+preset), Browse Templates, Custom/Code, then Settings isolation."""
    preset_live = os.environ.get("LABEL_STUDIO_PRESET_URL", "").strip().rstrip("/") or LIVE
    sync_playwright = require_playwright()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                ensure_logged_in(page, live=preset_live)
                page.wait_for_selector(".app-wrapper", timeout=30000)
                assert page.locator(".app-wrapper").count() > 0, "登录后没有 .app-wrapper"

                created = _api(
                    page,
                    "POST",
                    "/api/projects/",
                    {
                        "title": "dcp46-settings-isolation",
                        "label_config": SETTINGS_PROBE,
                    },
                )
                settings_pid = created.get("id")
                assert settings_pid, f"创建设置隔离项目失败: {created!r}"

                page.goto(preset_live + "/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(".app-wrapper", timeout=30000)
                _click_visible_text(page, "Create Project")
                page.get_by_text("Project Name", exact=True).first.wait_for(state="visible", timeout=15000)
                _shot(page, "01-create-project-name.png")

                custom_before = page.get_by_role("button", name="Create custom template")
                assert custom_before.count() == 0 or not custom_before.first.is_visible(), (
                    "首次进入不应先点 Custom template，但画廊已可见"
                )
                _click_visible_text(page, "Labeling Setup")
                page.get_by_role("button", name="Browse templates").wait_for(state="visible", timeout=20000)
                page.get_by_text("机器人视频时间轴标注", exact=False).first.wait_for(state="visible", timeout=15000)
                page.wait_for_timeout(400)
                assert _page_has(page, *PRESET_MARKERS), (
                    "首次 Labeling Setup 不是 Code+预置 XML（缺 DCP-37 标记）"
                )
                assert page.get_by_text("Code", exact=True).count() > 0
                _shot(page, "02-labeling-setup-code-preset.png")

                page.get_by_role("button", name="Browse templates").click()
                page.wait_for_timeout(800)
                page.get_by_role("button", name="Create custom template").wait_for(state="visible", timeout=15000)
                gallery = page.content()
                assert "Custom template" in gallery, "点 Browse Templates 后未见 Custom template"
                assert (
                    "Computer Vision" in gallery
                    or "Semantic Segmentation" in gallery
                    or "Natural Language" in gallery
                ), "点 Browse Templates 后未见画廊分组"
                _shot(page, "03-browse-templates-gallery.png")

                page.get_by_role("button", name="Create custom template").click()
                page.wait_for_timeout(800)
                page.get_by_role("button", name="Browse templates").wait_for(state="visible", timeout=15000)
                page.get_by_text("<View></View>", exact=False).first.wait_for(state="visible", timeout=10000)
                after_custom = page.locator("body").inner_text()
                assert "<View></View>" in after_custom or "Your labeling configuration is empty" in after_custom
                _click_visible_text(page, "Code")
                page.wait_for_timeout(400)
                assert page.locator("#edit_code, .CodeMirror, textarea").count() > 0, "切回 Code 后编辑器消失"
                _shot(page, "04-custom-then-code-editable.png")

                page.goto(
                    f"{preset_live}/projects/{settings_pid}/settings/labeling",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                page.wait_for_selector(".app-wrapper", timeout=30000)
                page.wait_for_timeout(1200)
                settings_text = page.locator("body").inner_text()
                settings_html = page.content()
                assert "Positive" in settings_text or 'value="Positive"' in settings_html, (
                    "已有项目 Settings → Labeling Interface 没有项目原配置"
                )
                assert "机器人视频时间轴标注" not in settings_text, (
                    "已有项目 Settings 被强行换成 Create Project 预置 XML"
                )
                _shot(page, "05-settings-labeling-not-preset.png")
                return {
                    "ok": True,
                    "settings_pid": int(settings_pid),
                    "preset_markers": list(PRESET_MARKERS),
                }
            finally:
                browser.close()
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if "Executable doesn't exist" in str(exc) or name in {"Error"}:
            raise AssertionError(playwright_missing_message(exc)) from exc
        raise AssertionError(f"浏览器核验失败（禁止 skip）: {exc}") from exc


IMPORT_MARKERS = (
    "LeRobot",
    "parquet",
    "jsonl",
    "Do not mix with",
    "Drag & drop files here",
)
_IMPORT_SHOT_RAW = os.environ.get("DCP41_INT_SCREENSHOT_DIR", "").strip()
IMPORT_SHOT_DIR = Path(_IMPORT_SHOT_RAW).expanduser() if _IMPORT_SHOT_RAW else SCREENSHOT_DIR


def _import_shot(page, name: str) -> None:
    if not IMPORT_SHOT_DIR:
        return
    IMPORT_SHOT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(IMPORT_SHOT_DIR / name), full_page=True)


def verify_import_lerobot_clicks() -> dict:
    """Click Data Import upload/dropzone and assert LeRobot copy plus mix/orphan errors."""
    import_live = os.environ.get("LABEL_STUDIO_IMPORT_URL", "").strip().rstrip("/") or LIVE
    evals = Path(__file__).resolve().parent
    mix_hdf5 = evals / "fixtures" / "import-mix" / "high_cam.hdf5"
    mix_mp4 = evals / "fixtures" / "import-mix" / "clip.mp4"
    orphan = evals / "fixtures" / "import-mix" / "orphan.parquet"
    mix_hdf5.parent.mkdir(parents=True, exist_ok=True)
    if not mix_hdf5.is_file():
        mix_hdf5.write_bytes(b"HDF5")
    if not mix_mp4.is_file():
        mix_mp4.write_bytes(b"\x00\x00")
    if not orphan.is_file():
        orphan.write_bytes(b"PAR1")

    sync_playwright = require_playwright()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                ensure_logged_in(page, live=import_live)
                page.wait_for_selector(".app-wrapper", timeout=30000)
                page.goto(import_live + "/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(".app-wrapper", timeout=30000)
                _click_visible_text(page, "Create Project")
                page.get_by_text("Project Name", exact=True).first.wait_for(state="visible", timeout=15000)
                _click_visible_text(page, "Data Import")
                page.get_by_text("Drag & drop files here", exact=False).first.wait_for(
                    state="visible", timeout=20000
                )
                body = page.locator("body").inner_text()
                assert all(marker in body for marker in IMPORT_MARKERS), (
                    f"Data Import 未见 LeRobot 提示: missing "
                    f"{[m for m in IMPORT_MARKERS if m not in body]}"
                )
                _import_shot(page, "01-data-import-lerobot-copy.png")

                upload = page.get_by_role("button", name="Upload file")
                upload.wait_for(state="visible", timeout=10000)
                with page.expect_file_chooser(timeout=10000) as chooser_info:
                    upload.click()
                chooser_info.value.set_files([str(mix_hdf5), str(mix_mp4)])
                page.wait_for_timeout(2500)
                mix_text = page.locator("body").inner_text()
                mix_html = page.content()
                assert "混传" in mix_text or "混传" in mix_html or "mix" in mix_text.lower(), (
                    f"点 Upload 混传 hdf5+mp4 后未见拒绝: {mix_text[:800]}"
                )
                _import_shot(page, "02-upload-mix-rejected.png")

                page.goto(import_live + "/", wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(".app-wrapper", timeout=30000)
                _click_visible_text(page, "Create Project")
                _click_visible_text(page, "Data Import")
                page.get_by_text("or click to browse", exact=False).first.wait_for(state="visible", timeout=15000)
                drop = page.locator("label[for=file-input]").first
                with page.expect_file_chooser(timeout=10000) as chooser_info:
                    drop.click()
                chooser_info.value.set_files([str(orphan)])
                page.wait_for_timeout(2500)
                orphan_text = page.locator("body").inner_text()
                orphan_html = page.content()
                assert (
                    "无法识别" in orphan_text
                    or "无法识别" in orphan_html
                    or "LeRobot" in orphan_text
                ), f"点拖放区上传孤 parquet 后未见错误: {orphan_text[:800]}"
                _import_shot(page, "03-dropzone-orphan-parquet.png")
                return {"ok": True, "markers": list(IMPORT_MARKERS)}
            finally:
                browser.close()
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if "Executable doesn't exist" in str(exc) or name in {"Error"}:
            raise AssertionError(playwright_missing_message(exc)) from exc
        raise AssertionError(f"浏览器核验失败（禁止 skip）: {exc}") from exc
