#!/usr/bin/env python3
"""Validate Zhiyuan robot-video overlay fixtures. No Label Studio core required."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED_LABELS = ("Static", "reach_object", "grasp_object", "place_object", "End")
FORBIDDEN_OLD_PHASE_LABELS = ("grasp", "Place")
MULTI_VIEW_LABELS = ("Static", "grasp", "Place", "End")
FORBIDDEN_SINGLE_VIEW = ("异常", "abnormal")
REMOVED_CONTROL_NAMES = ("granularity", "action_sequence")
DISCARD_LABEL = "废弃"
DISCARD_NAME = "discard"
PHASE_NAME = "videoLabels"
QUALITY_NAME = "actionQuality"
QUALITY_LABEL = "质量=0"
OVERLAY_DIR = Path(__file__).resolve().parent
SINGLE_VIEW = OVERLAY_DIR / "configs" / "single-view.xml"
SINGLE_VIEW_RLDS = OVERLAY_DIR / "configs" / "single-view-rlds.xml"
MULTI_VIEW = OVERLAY_DIR / "configs" / "multi-view.xml"
TASKS = OVERLAY_DIR / "examples" / "tasks-single-view.json"
EXPORT = OVERLAY_DIR / "examples" / "annotation-export.json"

CONTRACT_SUBTASKS = [
    {"name": "Static", "start_frame": 0, "end_frame": 2},
    {"name": "reach_object", "start_frame": 3, "end_frame": 5},
    {"name": "grasp_object", "start_frame": 6, "end_frame": 8},
    {"name": "place_object", "start_frame": 9, "end_frame": 11},
    {"name": "End", "start_frame": 12, "end_frame": 14},
]
CONTRACT_QUALITY_ZERO_FRAMES = frozenset({5, 6})
CONTRACT_T = 15


class CheckError(Exception):
    pass


def _local(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_config(path: Path) -> ET.Element:
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        raise CheckError(f"{path.name}: XML 不合法: {exc}") from exc
    root = tree.getroot()
    if _local(root.tag) != "View":
        raise CheckError(f"{path.name}: 根节点必须是 View，实际是 {_local(root.tag)}")
    return root


def findall(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == name]


def _document_order(root: ET.Element) -> list[ET.Element]:
    return list(root.iter())


def _element_index(root: ET.Element, target: ET.Element) -> int | None:
    for index, element in enumerate(_document_order(root)):
        if element is target:
            return index
    return None


def _first_index(root: ET.Element, name: str) -> int | None:
    for index, element in enumerate(_document_order(root)):
        if _local(element.tag) == name:
            return index
    return None


def _all_choice_values(root: ET.Element) -> list[str]:
    return [el.attrib.get("value") or "" for el in findall(root, "Choice")]


def _closed_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end


def check_single_view(root: ET.Element) -> None:
    videos = findall(root, "Video")
    timelines = findall(root, "TimelineLabels")
    if len(videos) != 1:
        raise CheckError(f"单视角必须恰好 1 个 Video，实际 {len(videos)}")
    if len(timelines) != 2:
        raise CheckError(
            f"单视角必须恰好 2 条 TimelineLabels（子任务轴 + 质量轴），实际 {len(timelines)}"
        )
    video = videos[0]
    if video.attrib.get("value") != "$video":
        raise CheckError("单视角 Video.value 必须是 $video")
    if not video.attrib.get("frameRate"):
        raise CheckError("单视角 Video 必须声明 frameRate")

    by_name = {el.attrib.get("name"): el for el in timelines}
    if set(by_name) != {PHASE_NAME, QUALITY_NAME}:
        raise CheckError(
            f"单视角 TimelineLabels.name 必须是 {PHASE_NAME!r} 与 {QUALITY_NAME!r}，实际 {sorted(by_name)}"
        )
    phase = by_name[PHASE_NAME]
    quality = by_name[QUALITY_NAME]
    video_name = video.attrib.get("name")
    if phase.attrib.get("toName") != video_name:
        raise CheckError("子任务 TimelineLabels.toName 必须指向 Video.name")
    if quality.attrib.get("toName") != video_name:
        raise CheckError("质量轴 TimelineLabels.toName 必须指向 Video.name")

    labels = [el.attrib.get("value") for el in findall(phase, "Label")]
    if tuple(labels) != REQUIRED_LABELS:
        missing = [name for name in REQUIRED_LABELS if name not in labels]
        if missing:
            raise CheckError(f"预置标签缺少字面量: {missing}；实际 {labels}")
        raise CheckError(f"子任务轴 Label 必须恰好为 {list(REQUIRED_LABELS)}，实际 {labels}")
    forbidden = [name for name in labels if name in FORBIDDEN_OLD_PHASE_LABELS]
    if forbidden:
        raise CheckError(f"单视角不得再预置旧阶段标签 {forbidden}")
    if DISCARD_LABEL in labels:
        raise CheckError("废弃不得做成 TimelineLabels 区间标签")
    if QUALITY_LABEL in labels:
        raise CheckError("质量=0 不得出现在子任务轴")

    quality_labels = [el.attrib.get("value") for el in findall(quality, "Label")]
    if quality_labels != [QUALITY_LABEL]:
        raise CheckError(f"质量轴只能有 Label {QUALITY_LABEL!r}，实际 {quality_labels}")

    videos_index = _first_index(root, "Video")
    phase_index = _element_index(root, phase)
    discard = [el for el in findall(root, "Choices") if el.attrib.get("name") == DISCARD_NAME]
    if len(discard) != 1:
        raise CheckError(f"单视角必须恰好 1 个 name=discard 的 Choices，实际 {len(discard)}")
    discard_values = [el.attrib.get("value") for el in findall(discard[0], "Choice")]
    if discard_values != [DISCARD_LABEL]:
        raise CheckError(f"discard 只能有「废弃」，实际 {discard_values}")
    discard_index = _element_index(root, discard[0])
    if videos_index is None or discard_index is None or discard_index >= videos_index:
        raise CheckError("废弃必须与阶段标签同在 Video 之前的顶部栏，不得放在页面下方")
    if phase_index is None or phase_index >= videos_index:
        raise CheckError("子任务轴必须在 Video 之前的顶部栏")

    banned = [value for value in _all_choice_values(root) if value in FORBIDDEN_SINGLE_VIEW]
    if banned:
        raise CheckError(f"单视角不得再预置 {banned}")

    for name in REMOVED_CONTROL_NAMES:
        if any(el.attrib.get("name") == name for el in findall(root, "Choices")):
            raise CheckError(f"单视角不得再预置 {name}")
        if any(el.attrib.get("name") == name for el in findall(root, "TextArea")):
            raise CheckError(f"单视角不得再预置 {name}")
    if findall(root, "TextArea"):
        raise CheckError("单视角不得再预置 TextArea（动作序列）")


def check_single_view_rlds(root: ET.Element) -> None:
    check_single_view(root)
    videos = findall(root, "Video")
    rate = (videos[0].attrib.get("frameRate") or "").strip()
    if not rate.startswith("10"):
        raise CheckError(f"RLDS 单视角 frameRate 必须是 10，实际 {rate}")


def check_multi_view(root: ET.Element) -> None:
    videos = findall(root, "Video")
    timelines = findall(root, "TimelineLabels")
    if len(videos) < 2:
        raise CheckError(f"多视角至少 2 个 Video，实际 {len(videos)}")
    if len(timelines) != 1:
        raise CheckError(f"多视角必须恰好 1 条 TimelineLabels，实际 {len(timelines)}")
    labels = [el.attrib.get("value") for el in findall(timelines[0], "Label")]
    missing = [name for name in MULTI_VIEW_LABELS if name not in labels]
    if missing:
        raise CheckError(f"多视角预置标签缺少字面量: {missing}")
    to_name = timelines[0].attrib.get("toName")
    video_names = [el.attrib.get("name") for el in videos]
    if to_name not in video_names:
        raise CheckError("多视角 TimelineLabels.toName 必须指向某个 Video.name")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckError(f"{path.name}: JSON 不合法: {exc}") from exc


def check_tasks(payload) -> None:
    if not isinstance(payload, list) or not payload:
        raise CheckError("示例任务必须是非空 JSON 数组")
    for index, task in enumerate(payload):
        if not isinstance(task, dict):
            raise CheckError(f"任务[{index}] 必须是对象")
        if "video" not in task:
            raise CheckError(f"任务[{index}] 缺少 video 字段")
        if not task["video"]:
            raise CheckError(f"任务[{index}] video 字段为空")


def reject_task_missing_video() -> None:
    try:
        check_tasks([{"id": 1}])
    except CheckError as exc:
        if "缺少 video 字段" not in str(exc):
            raise CheckError(f"缺 video 的错误原因不对: {exc}") from exc
        return
    raise CheckError("缺 video 字段的任务应当被拒绝")


def extract_results(payload) -> list:
    """Accept fixture `{result: [...]}` or official Export task array."""
    if isinstance(payload, dict) and "result" in payload:
        result = payload["result"]
        if not isinstance(result, list):
            raise CheckError("result 必须是列表")
        return result
    if isinstance(payload, list):
        collected: list = []
        for task in payload:
            if not isinstance(task, dict):
                raise CheckError("官方 Export 必须是 task 对象数组")
            for annotation in task.get("annotations") or []:
                items = annotation.get("result")
                if items is None:
                    continue
                if not isinstance(items, list):
                    raise CheckError("annotations[].result 必须是列表")
                collected.extend(items)
        return collected
    raise CheckError("无法识别标注形状：需要 {result: [...]} 或官方 Export 数组")


def timeline_segments(result: list, from_name: str | None = None) -> list[dict]:
    segments = []
    for item in result:
        if item.get("type") != "timelinelabels":
            continue
        if from_name is not None and item.get("from_name") != from_name:
            continue
        value = item.get("value") or {}
        ranges = value.get("ranges") or []
        names = value.get("timelinelabels") or []
        if not ranges or not names:
            raise CheckError("时间轴结果必须同时有 ranges 与 timelinelabels")
        for span in ranges:
            start = span.get("start")
            end = span.get("end")
            if start is None or end is None:
                raise CheckError("ranges 必须含 start/end")
            segments.append({"label": names[0], "start": start, "end": end})
    return segments


def _reject_phase_overlap(result: list) -> None:
    segments = timeline_segments(result, from_name=PHASE_NAME)
    for index, left in enumerate(segments):
        for right in segments[index + 1 :]:
            if _closed_overlap(left["start"], left["end"], right["start"], right["end"]):
                raise CheckError(f"子任务切段禁止重叠: {left} 与 {right}")


def check_annotation_shape(payload) -> list[dict]:
    """LS result field shape. Phase overlap is rejected; empty / partial remain parseable."""
    result = extract_results(payload)
    if result == []:
        return []
    for item in result:
        if not isinstance(item, dict):
            raise CheckError("result 条目必须是对象")
        for key in ("from_name", "to_name", "type", "value"):
            if key not in item:
                raise CheckError(f"result 条目缺少 {key}")
        if item["type"] == "timelinelabels":
            value = item.get("value") or {}
            if "ranges" not in value or "timelinelabels" not in value:
                raise CheckError("时间轴结果必须含 ranges 与 timelinelabels")
    _reject_phase_overlap(result)
    return timeline_segments(result, from_name=PHASE_NAME)


def check_export_fixture(payload) -> list[dict]:
    """Integrity of examples/annotation-export.json: contract array, not official LS result."""
    if isinstance(payload, dict) and "result" in payload:
        raise CheckError("导出夹具必须是合同数组，不是含 result 的官方 Export 形状")
    if not isinstance(payload, list) or not payload:
        raise CheckError("导出夹具必须是非空合同 JSON 数组")
    episode = payload[0]
    if not isinstance(episode, dict):
        raise CheckError("合同数组元素必须是对象")
    episode_id = episode.get("episode_id")
    if not episode_id or not isinstance(episode_id, str):
        raise CheckError("合同元素必须含非空 episode_id")
    subtasks = episode.get("subtasks")
    if not isinstance(subtasks, list) or not subtasks:
        raise CheckError("合同元素必须含非空 subtasks")
    names = []
    for index, item in enumerate(subtasks):
        if not isinstance(item, dict):
            raise CheckError(f"subtasks[{index}] 必须是对象")
        name = item.get("name")
        start = item.get("start_frame")
        end = item.get("end_frame")
        if name not in REQUIRED_LABELS:
            raise CheckError(f"subtasks[{index}].name 不在合同词表: {name}")
        if not isinstance(start, int) or not isinstance(end, int):
            raise CheckError(f"subtasks[{index}] 的 start_frame/end_frame 必须是整数")
        if start > end:
            raise CheckError(f"subtasks[{index}] start_frame 不能大于 end_frame")
        names.append(name)
        if index == 0 and start != 0:
            raise CheckError("第一段必须 start_frame=0")
        if index > 0:
            prev = subtasks[index - 1]
            if prev["end_frame"] + 1 != start:
                raise CheckError("相邻子任务必须 end_frame+1 == 下一段 start_frame（禁止重叠留空）")
    missing = [name for name in REQUIRED_LABELS if name not in names]
    if missing:
        raise CheckError(f"导出夹具缺少子任务 {missing}")

    attrs = episode.get("frame_attributes")
    if not isinstance(attrs, dict) or not attrs:
        raise CheckError("合同元素必须含 frame_attributes")
    last_end = subtasks[-1]["end_frame"]
    expected_keys = {str(frame) for frame in range(last_end + 1)}
    actual_keys = set(attrs)
    if actual_keys != expected_keys:
        raise CheckError(f"frame_attributes key 必须覆盖 0…{last_end}，实际 {sorted(actual_keys, key=int)}")
    for key, frame in attrs.items():
        if not isinstance(frame, dict):
            raise CheckError(f"frame_attributes[{key!r}] 必须是对象")
        quality = frame.get("action_quality")
        if quality not in (0, 1):
            raise CheckError(f"frame_attributes[{key!r}].action_quality 必须是 0 或 1")

    if last_end + 1 != CONTRACT_T:
        raise CheckError(f"导出夹具 T 必须是 {CONTRACT_T}，实际 {last_end + 1}")
    if subtasks != CONTRACT_SUBTASKS:
        raise CheckError(f"导出夹具 subtasks 与合同示例不符: {subtasks}")
    zero_frames = {int(key) for key, frame in attrs.items() if frame.get("action_quality") == 0}
    if zero_frames != CONTRACT_QUALITY_ZERO_FRAMES:
        raise CheckError(f"导出夹具质量=0 帧必须是 {sorted(CONTRACT_QUALITY_ZERO_FRAMES)}，实际 {sorted(zero_frames)}")
    return subtasks


def check_empty_annotation_allowed() -> None:
    if check_annotation_shape({"result": []}) != []:
        raise CheckError("空标注应得到空区间列表")


def check_whole_only_allowed() -> None:
    segments = check_annotation_shape(
        {
            "result": [
                {
                    "from_name": DISCARD_NAME,
                    "to_name": "video",
                    "type": "choices",
                    "value": {"choices": [DISCARD_LABEL]},
                }
            ]
        }
    )
    if segments:
        raise CheckError("只有整段废弃时不应解析出时间轴区间")


def check_partial_timeline_allowed() -> None:
    segments = check_annotation_shape(
        {
            "result": [
                {
                    "from_name": PHASE_NAME,
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 1, "end": 10}],
                        "timelinelabels": ["Static"],
                    },
                },
                {
                    "from_name": PHASE_NAME,
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 11, "end": 20}],
                        "timelinelabels": ["grasp_object"],
                    },
                },
            ]
        }
    )
    if [item["label"] for item in segments] != ["Static", "grasp_object"]:
        raise CheckError(f"部分区间应被接受: {segments}")


def check_overlap_rejected() -> None:
    payload = {
        "result": [
            {
                "from_name": PHASE_NAME,
                "to_name": "video",
                "type": "timelinelabels",
                "value": {
                    "ranges": [{"start": 10, "end": 30}],
                    "timelinelabels": ["grasp_object"],
                },
            },
            {
                "from_name": PHASE_NAME,
                "to_name": "video",
                "type": "timelinelabels",
                "value": {
                    "ranges": [{"start": 20, "end": 40}],
                    "timelinelabels": ["place_object"],
                },
            },
        ]
    }
    try:
        check_annotation_shape(payload)
    except CheckError as exc:
        if "重叠" not in str(exc):
            raise CheckError(f"重叠应因切段重叠被拒绝，实际: {exc}") from exc
        return
    raise CheckError("重叠切段应当被拒绝")


def check_official_export_shape_rejected_as_fixture() -> None:
    try:
        check_export_fixture({"result": []})
    except CheckError as exc:
        if "合同数组" not in str(exc) and "官方" not in str(exc):
            raise CheckError(f"官方 result 形状应被导出夹具拒绝，实际: {exc}") from exc
        return
    raise CheckError("官方 result 形状不得作为导出夹具")


def check_quality_span_may_cross_subtasks() -> None:
    segments = check_annotation_shape(
        {
            "result": [
                {
                    "from_name": PHASE_NAME,
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 1, "end": 10}],
                        "timelinelabels": ["reach_object"],
                    },
                },
                {
                    "from_name": PHASE_NAME,
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 11, "end": 20}],
                        "timelinelabels": ["grasp_object"],
                    },
                },
                {
                    "from_name": QUALITY_NAME,
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 8, "end": 14}],
                        "timelinelabels": [QUALITY_LABEL],
                    },
                },
            ]
        }
    )
    if [item["label"] for item in segments] != ["reach_object", "grasp_object"]:
        raise CheckError(f"质量轴跨界不应改写子任务段: {segments}")


def check_discard_is_not_a_timeline_span() -> None:
    payload = {
        "result": [
            {
                "from_name": DISCARD_NAME,
                "to_name": "video",
                "type": "choices",
                "value": {"choices": [DISCARD_LABEL]},
            },
            {
                "from_name": PHASE_NAME,
                "to_name": "video",
                "type": "timelinelabels",
                "value": {
                    "ranges": [{"start": 1, "end": 10}],
                    "timelinelabels": ["Static"],
                },
            },
        ]
    }
    segments = check_annotation_shape(payload)
    if [item["label"] for item in segments] != ["Static"]:
        raise CheckError(f"废弃不应出现在时间轴区间里: {segments}")
    check_no_discard_timeline_segments(payload)


def check_no_discard_timeline_segments(payload) -> None:
    result = extract_results(payload)
    for item in result:
        if item.get("type") != "timelinelabels":
            continue
        names = (item.get("value") or {}).get("timelinelabels") or []
        if DISCARD_LABEL in names:
            raise CheckError("废弃不得导出为 timelinelabels 区间")


def check_discard_as_timeline_is_rejected() -> None:
    payload = {
        "result": [
            {
                "from_name": PHASE_NAME,
                "to_name": "video",
                "type": "timelinelabels",
                "value": {
                    "ranges": [{"start": 1, "end": 10}],
                    "timelinelabels": [DISCARD_LABEL],
                },
            }
        ]
    }
    try:
        check_no_discard_timeline_segments(payload)
    except CheckError as exc:
        if "不得导出为 timelinelabels" not in str(exc):
            raise
        return
    raise CheckError("把废弃写成时间轴区间应当被拒绝")


def run_all() -> list[str]:
    errors: list[str] = []

    def capture(name: str, fn) -> None:
        try:
            fn()
        except CheckError as exc:
            errors.append(f"{name}: {exc}")

    capture("single-view", lambda: check_single_view(parse_config(SINGLE_VIEW)))
    capture("single-view-rlds", lambda: check_single_view_rlds(parse_config(SINGLE_VIEW_RLDS)))
    capture("multi-view", lambda: check_multi_view(parse_config(MULTI_VIEW)))
    capture("tasks", lambda: check_tasks(load_json(TASKS)))
    capture("export-fixture", lambda: check_export_fixture(load_json(EXPORT)))
    capture("missing-video", reject_task_missing_video)
    capture("empty-annotation", check_empty_annotation_allowed)
    capture("whole-only", check_whole_only_allowed)
    capture("partial-timeline", check_partial_timeline_allowed)
    capture("overlap", check_overlap_rejected)
    capture("official-export-rejected", check_official_export_shape_rejected_as_fixture)
    capture("quality-crosses", check_quality_span_may_cross_subtasks)
    capture("discard-choices", check_discard_is_not_a_timeline_span)
    capture("discard-not-span", check_discard_as_timeline_is_rejected)
    return errors


def main() -> int:
    errors = run_all()
    if errors:
        print("FAIL")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PASS")
    print(
        "checked: single-view, single-view-rlds, multi-view, tasks, export-fixture, "
        "missing-video, empty-annotation, whole-only, partial-timeline, "
        "overlap, official-export-rejected, quality-crosses, discard-choices, discard-not-span"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
