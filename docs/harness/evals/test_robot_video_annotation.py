"""Eval for Zhiyuan robot-video overlay. Contract: five labels + quality axis + contract JSON."""

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

VALID_SINGLE_VIEW_XML = """
<View>
  <TimelineLabels name="videoLabels" toName="video">
    <Label value="Static"/>
    <Label value="reach_object"/>
    <Label value="grasp_object"/>
    <Label value="place_object"/>
    <Label value="End"/>
  </TimelineLabels>
  <Choices name="discard" toName="video"><Choice value="废弃"/></Choices>
  <Video name="video" value="$video" frameRate="30.0"/>
  <TimelineLabels name="actionQuality" toName="video">
    <Label value="质量=0"/>
  </TimelineLabels>
</View>
"""


def test_single_view_has_two_timelines_and_required_labels():
    overlay.check_single_view(overlay.parse_config(overlay.SINGLE_VIEW))
    root = overlay.parse_config(overlay.SINGLE_VIEW)
    timelines = overlay.findall(root, "TimelineLabels")
    assert len(timelines) == 2
    names = [el.attrib.get("name") for el in timelines]
    assert names == ["videoLabels", "actionQuality"]
    phase_labels = [el.attrib.get("value") for el in overlay.findall(timelines[0], "Label")]
    assert phase_labels == list(overlay.REQUIRED_LABELS)
    assert overlay.findall(timelines[1], "Label")[0].attrib.get("value") == "质量=0"
    xml_text = overlay.SINGLE_VIEW.read_text(encoding="utf-8")
    assert "granularity" not in xml_text
    assert "action_sequence" not in xml_text
    assert 'value="grasp"' not in xml_text
    assert 'value="Place"' not in xml_text


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


def test_export_fixture_is_contract_array():
    payload = overlay.load_json(overlay.EXPORT)
    subtasks = overlay.check_export_fixture(payload)
    assert isinstance(payload, list)
    assert payload[0]["episode_id"] == "episode_000000"
    assert subtasks == overlay.CONTRACT_SUBTASKS
    attrs = payload[0]["frame_attributes"]
    assert set(attrs) == {str(frame) for frame in range(15)}
    assert {int(key) for key, frame in attrs.items() if frame["action_quality"] == 0} == {5, 6}


def test_annotation_shape_empty_partial_and_overlap_rejected():
    overlay.check_empty_annotation_allowed()
    overlay.check_whole_only_allowed()
    overlay.check_partial_timeline_allowed()
    overlay.check_overlap_rejected()
    overlay.check_official_export_shape_rejected_as_fixture()
    overlay.check_quality_span_may_cross_subtasks()


def test_quality_axis_is_required():
    root = overlay.parse_config(overlay.SINGLE_VIEW)
    assert len(overlay.findall(root, "TimelineLabels")) == 2
    names = [el.attrib.get("name") for el in overlay.findall(root, "Choices")]
    assert "granularity" not in names
    assert "discard" in names


def test_single_timeline_is_rejected():
    xml = """
    <View>
      <TimelineLabels name="videoLabels" toName="video">
        <Label value="Static"/>
        <Label value="reach_object"/>
        <Label value="grasp_object"/>
        <Label value="place_object"/>
        <Label value="End"/>
      </TimelineLabels>
      <Choices name="discard" toName="video"><Choice value="废弃"/></Choices>
      <Video name="video" value="$video" frameRate="30.0"/>
    </View>
    """
    root = ET.fromstring(xml)
    try:
        overlay.check_single_view(root)
    except overlay.CheckError as exc:
        assert "恰好 2 条 TimelineLabels" in str(exc)
    else:
        raise AssertionError("缺少质量轴应失败")


def test_wrong_label_case_is_rejected():
    xml = """
    <View>
      <TimelineLabels name="videoLabels" toName="video">
        <Label value="static"/>
        <Label value="reach_object"/>
        <Label value="grasp_object"/>
        <Label value="place_object"/>
        <Label value="end"/>
      </TimelineLabels>
      <Choices name="discard" toName="video"><Choice value="废弃"/></Choices>
      <Video name="video" value="$video" frameRate="30.0"/>
      <TimelineLabels name="actionQuality" toName="video">
        <Label value="质量=0"/>
      </TimelineLabels>
    </View>
    """
    root = ET.fromstring(xml)
    try:
        overlay.check_single_view(root)
    except overlay.CheckError as exc:
        assert "缺少字面量" in str(exc) or "必须恰好为" in str(exc)
    else:
        raise AssertionError("错误大小写应失败")


def test_inline_contract_xml_passes():
    overlay.check_single_view(ET.fromstring(VALID_SINGLE_VIEW_XML))


def test_run_all_pass_rate():
    errors = overlay.run_all()
    assert not errors, errors
    total = 14
    passed = total - len(errors)
    assert passed / total >= 0.8


def _run_standalone() -> int:
    tests = [
        test_single_view_has_two_timelines_and_required_labels,
        test_multi_view_structure,
        test_tasks_require_video_field,
        test_export_fixture_is_contract_array,
        test_annotation_shape_empty_partial_and_overlap_rejected,
        test_quality_axis_is_required,
        test_single_timeline_is_rejected,
        test_wrong_label_case_is_rejected,
        test_inline_contract_xml_passes,
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
