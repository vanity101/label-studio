#!/usr/bin/env python3
"""Validate Zhiyuan robot-video overlay fixtures. No Label Studio core required."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REQUIRED_LABELS = ("Static", "grasp", "Place", "End")
FORBIDDEN_SINGLE_VIEW = ("异常", "abnormal")
DISCARD_LABEL = "废弃"
DISCARD_NAME = "discard"
OVERLAY_DIR = Path(__file__).resolve().parent
SINGLE_VIEW = OVERLAY_DIR / "configs" / "single-view.xml"
SINGLE_VIEW_RLDS = OVERLAY_DIR / "configs" / "single-view-rlds.xml"
MULTI_VIEW = OVERLAY_DIR / "configs" / "multi-view.xml"
TASKS = OVERLAY_DIR / "examples" / "tasks-single-view.json"
EXPORT = OVERLAY_DIR / "examples" / "annotation-export.json"


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


def check_single_view(root: ET.Element) -> None:
    videos = findall(root, "Video")
    timelines = findall(root, "TimelineLabels")
    if len(videos) != 1:
        raise CheckError(f"单视角必须恰好 1 个 Video，实际 {len(videos)}")
    if len(timelines) != 1:
        raise CheckError(
            f"单视角必须恰好 1 条 TimelineLabels（细致度不是第二套时间轴），实际 {len(timelines)}"
        )
    video = videos[0]
    if video.attrib.get("value") != "$video":
        raise CheckError("单视角 Video.value 必须是 $video")
    if not video.attrib.get("frameRate"):
        raise CheckError("单视角 Video 必须声明 frameRate")
    timeline = timelines[0]
    if timeline.attrib.get("toName") != video.attrib.get("name"):
        raise CheckError("TimelineLabels.toName 必须指向 Video.name")
    labels = [el.attrib.get("value") for el in findall(timeline, "Label")]
    missing = [name for name in REQUIRED_LABELS if name not in labels]
    if missing:
        raise CheckError(f"预置标签缺少字面量: {missing}；实际 {labels}")
    extra_phase = [name for name in labels if name not in REQUIRED_LABELS]
    if extra_phase:
        raise CheckError(f"单视角起步模板不得预置阶段词表以外的 Label: {extra_phase}")
    if DISCARD_LABEL in labels:
        raise CheckError("废弃不得做成 TimelineLabels 区间标签")

    videos_index = _first_index(root, "Video")
    discard = [el for el in findall(root, "Choices") if el.attrib.get("name") == DISCARD_NAME]
    if len(discard) != 1:
        raise CheckError(f"单视角必须恰好 1 个 name=discard 的 Choices，实际 {len(discard)}")
    discard_values = [el.attrib.get("value") for el in findall(discard[0], "Choice")]
    if discard_values != [DISCARD_LABEL]:
        raise CheckError(f"discard 只能有「废弃」，实际 {discard_values}")
    discard_index = _element_index(root, discard[0])
    if videos_index is None or discard_index is None or discard_index >= videos_index:
        raise CheckError("废弃必须与阶段标签同在 Video 之前的顶部栏，不得放在页面下方")

    banned = [value for value in _all_choice_values(root) if value in FORBIDDEN_SINGLE_VIEW]
    if banned:
        raise CheckError(f"单视角不得再预置 {banned}")

    granularity = [el for el in findall(root, "Choices") if el.attrib.get("name") == "granularity"]
    if not granularity:
        raise CheckError("单视角必须有整段 Choices（细致度）")
    if not findall(root, "TextArea"):
        raise CheckError("单视角必须有整段 TextArea（动作序列）")


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
    missing = [name for name in REQUIRED_LABELS if name not in labels]
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


def timeline_segments(result: list) -> list[dict]:
    segments = []
    for item in result:
        if item.get("type") != "timelinelabels":
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


def check_annotation_shape(payload) -> list[dict]:
    """Official field shape only. Empty / whole-only / partial / overlap are allowed."""
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
    return timeline_segments(result)


def check_export_fixture(payload) -> list[dict]:
    """Integrity of examples/annotation-export.json only. Do not use on live Export."""
    if not isinstance(payload, dict) or "result" not in payload:
        raise CheckError("导出夹具必须是含 result 的对象，不是官方 Export 整包")
    segments = check_annotation_shape(payload)
    labels = [item["label"] for item in segments]
    for name in REQUIRED_LABELS:
        if name not in labels:
            raise CheckError(f"导出夹具缺少标签 {name}")
    if labels.count("Static") < 2:
        raise CheckError("导出夹具必须含两段 Static（片头 + 片尾）")
    whole = [item for item in payload["result"] if item.get("type") != "timelinelabels"]
    if not whole:
        raise CheckError("导出夹具必须同时含整段字段，以便与时间轴结果区分")
    expected = [
        {"label": "Static", "start": 1, "end": 20},
        {"label": "grasp", "start": 21, "end": 40},
        {"label": "Place", "start": 41, "end": 70},
        {"label": "End", "start": 71, "end": 90},
        {"label": "Static", "start": 91, "end": 120},
    ]
    if segments != expected:
        raise CheckError(f"导出夹具区间与约定不符: {segments}")
    return segments


def check_empty_annotation_allowed() -> None:
    if check_annotation_shape({"result": []}) != []:
        raise CheckError("空标注应得到空区间列表")


def check_whole_only_allowed() -> None:
    segments = check_annotation_shape(
        {
            "result": [
                {
                    "from_name": "granularity",
                    "to_name": "video",
                    "type": "choices",
                    "value": {"choices": ["简单"]},
                }
            ]
        }
    )
    if segments:
        raise CheckError("只有整段时不应解析出时间轴区间")


def check_partial_timeline_allowed() -> None:
    segments = check_annotation_shape(
        {
            "result": [
                {
                    "from_name": "videoLabels",
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 1, "end": 10}],
                        "timelinelabels": ["Static"],
                    },
                },
                {
                    "from_name": "videoLabels",
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 11, "end": 20}],
                        "timelinelabels": ["grasp"],
                    },
                },
            ]
        }
    )
    if [item["label"] for item in segments] != ["Static", "grasp"]:
        raise CheckError(f"部分区间应被接受: {segments}")


def check_overlap_allowed() -> None:
    check_annotation_shape(
        {
            "result": [
                {
                    "from_name": "videoLabels",
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 10, "end": 30}],
                        "timelinelabels": ["grasp"],
                    },
                },
                {
                    "from_name": "videoLabels",
                    "to_name": "video",
                    "type": "timelinelabels",
                    "value": {
                        "ranges": [{"start": 20, "end": 40}],
                        "timelinelabels": ["Place"],
                    },
                },
            ]
        }
    )


def check_official_export_package_allowed() -> None:
    fixture = load_json(EXPORT)
    package = [{"data": {"video": "/static/samples/opossum_snow.mp4"}, "annotations": [fixture]}]
    segments = check_annotation_shape(package)
    if len(segments) != 5:
        raise CheckError(f"官方整包应还原夹具区间，实际 {segments}")


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
                "from_name": "videoLabels",
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
                "from_name": "videoLabels",
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
    capture("overlap", check_overlap_allowed)
    capture("official-export-package", check_official_export_package_allowed)
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
        "overlap, official-export-package, discard-choices, discard-not-span"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
