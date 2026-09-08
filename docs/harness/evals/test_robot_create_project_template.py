"""Source contract for Create Project default Custom template (S2-T2 / FR-013…FR-018)."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CREATE = ROOT / "web/apps/labelstudio/src/pages/CreateProject/CreateProject.jsx"
CONFIG = ROOT / "web/apps/labelstudio/src/pages/CreateProject/Config/Config.jsx"
SETTINGS = ROOT / "web/apps/labelstudio/src/pages/Settings/LabelingSettings.jsx"
TEMPLATE = ROOT / "web/apps/labelstudio/src/pages/CreateProject/Config/robotDefaultTemplate.js"


def test_create_project_passes_preset_props():
    src = CREATE.read_text(encoding="utf-8")
    assert 'from "./Config/robotDefaultTemplate"' in src
    assert "defaultToCustomTemplate" in src
    assert "presetConfig={ROBOT_DEFAULT_TEMPLATE}" in src
    assert "LabelingSettings" not in src


def test_labeling_settings_does_not_pass_preset():
    src = SETTINGS.read_text(encoding="utf-8")
    assert "defaultToCustomTemplate" not in src
    assert "presetConfig" not in src
    assert "ROBOT_DEFAULT_TEMPLATE" not in src
    assert "<ConfigPage" in src


def test_config_page_bootstraps_view_and_code_from_preset():
    src = CONFIG.read_text(encoding="utf-8")
    assert "defaultToCustomTemplate" in src
    assert "presetConfig" in src
    assert "usePresetOnFirstView" in src
    assert "firstViewConfig" in src
    assert "preferCodeView" in src
    assert 'firstViewConfig ? "view" : "list"' in src
    bootstrap = src.split("export const ConfigPage", 1)[1]
    assert "setTemplate(EMPTY_CONFIG)" not in bootstrap.split("onCustomTemplate", 1)[0]
    assert "setTemplate(firstViewConfig)" in src
    assert "onBrowse" in src
    assert "Browse Templates" in src


def test_preset_xml_is_dcp37_not_overlay_30fps():
    xml = TEMPLATE.read_text(encoding="utf-8")
    assert 'frameRate="10.0"' in xml
    assert 'frameRate="30' not in xml
    assert 'value="Static"' in xml
    assert "ROBOT_DEFAULT_TEMPLATE" in xml


def main() -> int:
    tests = [
        test_create_project_passes_preset_props,
        test_labeling_settings_does_not_pass_preset,
        test_config_page_bootstraps_view_and_code_from_preset,
        test_preset_xml_is_dcp37_not_overlay_30fps,
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {test.__name__}")
            traceback.print_exc()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
