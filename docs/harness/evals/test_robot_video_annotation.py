"""Eval for Zhiyuan robot-video overlay. Contract: robot-video-annotation.md"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "docs" / "harness" / "overlays" / "zhiyuan-robot-video"
if str(OVERLAY) not in sys.path:
    sys.path.insert(0, str(OVERLAY))

import check_overlay as overlay  # noqa: E402


def test_single_view_has_one_timeline_and_required_labels():
    overlay.check_single_view(overlay.parse_config(overlay.SINGLE_VIEW))


def test_multi_view_structure():
    overlay.check_multi_view(overlay.parse_config(overlay.MULTI_VIEW))


def test_tasks_require_video_field():
    overlay.check_tasks(overlay.load_json(overlay.TASKS))
    overlay.reject_task_missing_video()
    try:
        overlay.check_tasks([{"id": 1}])
    except overlay.CheckError as exc:
        assert "缺少 video 字段" in str(exc)
    else:
        raise AssertionError("缺 video 应失败")


def test_export_fixture_restores_all_ranges():
    payload = overlay.load_json(overlay.EXPORT)
    segments = overlay.check_export_fixture(payload)
    assert segments == [
        {"label": "Static", "start": 1, "end": 20},
        {"label": "grasp", "start": 21, "end": 40},
        {"label": "Place", "start": 41, "end": 70},
        {"label": "End", "start": 71, "end": 90},
        {"label": "Static", "start": 91, "end": 120},
    ]


def test_annotation_shape_allows_empty_whole_partial_overlap_and_official_package():
    overlay.check_empty_annotation_allowed()
    overlay.check_whole_only_allowed()
    overlay.check_partial_timeline_allowed()
    overlay.check_overlap_allowed()
    overlay.check_official_export_package_allowed()


def test_granularity_is_not_a_second_timeline():
    root = overlay.parse_config(overlay.SINGLE_VIEW)
    assert len(overlay.findall(root, "TimelineLabels")) == 1
    names = [el.attrib.get("name") for el in overlay.findall(root, "Choices")]
    assert "granularity" in names


def test_second_timeline_is_rejected():
    xml = """
    <View>
      <TimelineLabels name="a" toName="video"><Label value="Static"/></TimelineLabels>
      <TimelineLabels name="b" toName="video"><Label value="grasp"/></TimelineLabels>
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


def test_wrong_label_case_is_rejected():
    xml = """
    <View>
      <TimelineLabels name="videoLabels" toName="video">
        <Label value="static"/>
        <Label value="grasp"/>
        <Label value="Place"/>
        <Label value="end"/>
      </TimelineLabels>
      <Video name="video" value="$video" frameRate="30.0"/>
      <Choices name="granularity" toName="video"><Choice value="简单"/></Choices>
      <TextArea name="action_sequence" toName="video"/>
    </View>
    """
    root = ET.fromstring(xml)
    try:
        overlay.check_single_view(root)
    except overlay.CheckError as exc:
        assert "缺少字面量" in str(exc)
    else:
        raise AssertionError("错误大小写应失败")


def test_run_all_pass_rate():
    errors = overlay.run_all()
    assert not errors, errors
    total = 12
    passed = total - len(errors)
    assert passed / total >= 0.8


def _run_standalone() -> int:
    tests = [
        test_single_view_has_one_timeline_and_required_labels,
        test_multi_view_structure,
        test_tasks_require_video_field,
        test_export_fixture_restores_all_ranges,
        test_annotation_shape_allows_empty_whole_partial_overlap_and_official_package,
        test_granularity_is_not_a_second_timeline,
        test_second_timeline_is_rejected,
        test_wrong_label_case_is_rejected,
        test_run_all_pass_rate,
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
