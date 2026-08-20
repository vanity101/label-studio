"""Eval for Zhiyuan robot-video flat outliner reorder. Contract: robot-video-ux-reorder.md"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video"
EDITOR = ROOT / "web" / "libs" / "editor" / "src"
if str(OVERLAY) not in sys.path:
    sys.path.insert(0, str(OVERLAY))

import check_overlay as overlay  # noqa: E402
import click_span  # noqa: E402
import flat_reorder  # noqa: E402
import test_robot_video_annotation as annotation_eval  # noqa: E402
import test_robot_video_ux as ux_eval  # noqa: E402
import test_robot_video_ux_runtime as runtime_eval  # noqa: E402


def test_move_before_first_row():
    assert flat_reorder.move_id(["static", "grasp", "place"], "place", "static", "before") == [
        "place",
        "static",
        "grasp",
    ]


def test_drop_on_body_is_before_not_nest():
    assert flat_reorder.drop_place(False, 0, 1) == "before"
    assert flat_reorder.drop_place(True, -1, 0) == "before"


def test_click_span_ignores_display_order():
    regions = [
        {"type": "timelineregion", "ouid": 3, "ranges": [{"start": 21, "end": 30}]},
        {"type": "timelineregion", "ouid": 1, "ranges": [{"start": 1, "end": 10}]},
        {"type": "timelineregion", "ouid": 2, "ranges": [{"start": 11, "end": 20}]},
    ]
    end = click_span.last_created_end(regions)
    assert end == 30
    assert click_span.next_click_span(end, 50) == (31, 50)


def test_outliner_is_wired_for_flat_timeline_reorder():
    store = (EDITOR / "stores" / "RegionStore.js").read_text(encoding="utf-8")
    tree = (EDITOR / "components" / "SidePanels" / "OutlinerPanel" / "OutlinerTree.tsx").read_text(
        encoding="utf-8"
    )
    helper = (
        EDITOR / "components" / "SidePanels" / "OutlinerPanel" / "flatReorder.js"
    ).read_text(encoding="utf-8")
    assert "applyFlatOutlinerOrder" in store
    assert "outlinerOrder" in store
    assert "shouldFlatReorder" in tree
    assert "applyFlatOutlinerOrder" in tree
    assert "timelineregion" in helper


def test_multi_view_xml_was_not_rewritten():
    ux_eval.test_multi_view_xml_was_not_rewritten()


def test_previous_evals_still_hold():
    overlay.check_single_view(overlay.parse_config(overlay.SINGLE_VIEW))
    annotation_eval.test_run_all_pass_rate()
    ux_eval.test_click_span_first_and_continue_and_overlap()
    runtime_eval.test_dockerfile_does_not_alias_vite_onto_webpack_main()


def _run_standalone() -> int:
    tests = [
        test_move_before_first_row,
        test_drop_on_body_is_before_not_nest,
        test_click_span_ignores_display_order,
        test_outliner_is_wired_for_flat_timeline_reorder,
        test_multi_view_xml_was_not_rewritten,
        test_previous_evals_still_hold,
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
