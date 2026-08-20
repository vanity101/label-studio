"""Eval for Zhiyuan robot-video UX. Contract: robot-video-ux.md"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video"
EDITOR = ROOT / "web" / "libs" / "editor" / "src"
if str(OVERLAY) not in sys.path:
    sys.path.insert(0, str(OVERLAY))

import check_overlay as overlay  # noqa: E402
import click_span  # noqa: E402


def test_click_span_first_and_continue_and_overlap():
    assert click_span.next_click_span(None, 17) == (1, 17)
    assert click_span.next_click_span(20, 40) == (21, 40)
    assert click_span.next_click_span(20, 10) == (10, 20)
    assert click_span.next_click_span(20, 20) == (20, 20)


def test_last_created_is_click_order_not_start_frame():
    end = click_span.last_created_end(
        [
            {"type": "timelineregion", "ouid": 2, "ranges": [{"start": 50, "end": 60}]},
            {"type": "timelineregion", "ouid": 1, "ranges": [{"start": 1, "end": 10}]},
        ]
    )
    assert end == 60
    assert click_span.next_click_span(end, 80) == (61, 80)


def test_discard_blocks_new_spans():
    assert click_span.can_create_span(False) is True
    assert click_span.can_create_span(True) is False


def test_single_view_discard_is_on_top_bar():
    root = overlay.parse_config(overlay.SINGLE_VIEW)
    overlay.check_single_view(root)
    video_index = overlay._first_index(root, "Video")
    timeline_index = overlay._first_index(root, "TimelineLabels")
    discard = [el for el in overlay.findall(root, "Choices") if el.attrib.get("name") == "discard"][0]
    discard_index = overlay._element_index(root, discard)
    assert timeline_index < video_index
    assert discard_index < video_index
    assert "异常" not in overlay._all_choice_values(root)
    assert "abnormal" not in overlay._all_choice_values(root)


def test_multi_view_xml_was_not_rewritten():
    root = overlay.parse_config(overlay.MULTI_VIEW)
    overlay.check_multi_view(root)
    values = overlay._all_choice_values(root)
    assert "异常" in values
    assert "abnormal" in values


def test_discard_export_is_choices_not_ranges():
    overlay.check_discard_is_not_a_timeline_span()
    overlay.check_discard_as_timeline_is_rejected()


def test_editor_click_to_span_is_wired():
    labels = (EDITOR / "tags" / "control" / "TimelineLabels.js").read_text(encoding="utf-8")
    interact = (EDITOR / "tags" / "control" / "Label.jsx").read_text(encoding="utf-8")
    editor = (
        EDITOR / "components" / "SidePanels" / "DetailsPanel" / "TimelineRegionEditor.tsx"
    ).read_text(encoding="utf-8")
    region_store = (EDITOR / "stores" / "RegionStore.js").read_text(encoding="utf-8")
    assert "handleLabelClick" in labels
    assert "nextClickSpan" in labels
    assert "handleLabelClick" in interact
    assert "applyPhaseLabel" in editor
    assert "ouid" in region_store
    assert 'enumeration(["date", "score", "mediaStartTime"])' in region_store


def test_dockerfile_is_official_image_plus_frontend():
    dockerfiles = [
        OVERLAY / "Dockerfile",
        ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video" / "Dockerfile",
    ]
    path = next(item for item in dockerfiles if item.exists())
    text = path.read_text(encoding="utf-8")
    assert "heartexlabs/label-studio" in text
    assert "web" in text.lower() or "frontend" in text.lower()


def test_previous_overlay_eval_still_holds():
    overlay.check_single_view(overlay.parse_config(overlay.SINGLE_VIEW))
    overlay.check_export_fixture(overlay.load_json(overlay.EXPORT))
    errors = overlay.run_all()
    assert not errors, errors


def test_second_timeline_still_rejected():
    xml = """
    <View>
      <TimelineLabels name="a" toName="video"><Label value="Static"/></TimelineLabels>
      <TimelineLabels name="b" toName="video"><Label value="grasp"/></TimelineLabels>
      <Choices name="discard" toName="video"><Choice value="废弃"/></Choices>
      <Video name="video" value="$video" frameRate="30.0"/>
      <Choices name="granularity" toName="video"><Choice value="简单"/></Choices>
      <TextArea name="action_sequence" toName="video"/>
    </View>
    """
    root = ET.fromstring(xml)
    try:
        overlay.check_single_view(root)
    except overlay.CheckError as exc:
        assert "恰好 1 条 TimelineLabels" in str(exc)
    else:
        raise AssertionError("第二套时间轴应失败")


def _run_standalone() -> int:
    tests = [
        test_click_span_first_and_continue_and_overlap,
        test_last_created_is_click_order_not_start_frame,
        test_discard_blocks_new_spans,
        test_single_view_discard_is_on_top_bar,
        test_multi_view_xml_was_not_rewritten,
        test_discard_export_is_choices_not_ranges,
        test_editor_click_to_span_is_wired,
        test_dockerfile_is_official_image_plus_frontend,
        test_previous_overlay_eval_still_holds,
        test_second_timeline_still_rejected,
    ]
    failed = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:  # noqa: BLE001 — eval runner must surface any failure
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
