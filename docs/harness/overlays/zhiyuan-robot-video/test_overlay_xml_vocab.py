#!/usr/bin/env python3
"""Narrow S1-T1 gate: overlay XML vocab + two TimelineLabels. Does not import check_overlay."""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

OVERLAY_DIR = Path(__file__).resolve().parent
SINGLE_VIEW = OVERLAY_DIR / "configs" / "single-view.xml"
SINGLE_VIEW_RLDS = OVERLAY_DIR / "configs" / "single-view-rlds.xml"

PHASE_LABELS = ("Static", "reach_object", "grasp_object", "place_object", "End")
FORBIDDEN_OLD_LABELS = ("grasp", "Place")
REMOVED_CONTROL_NAMES = ("granularity", "action_sequence")


def _local(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _findall(root: ET.Element, name: str) -> list[ET.Element]:
    return [el for el in root.iter() if _local(el.tag) == name]


def _parse(path: Path) -> ET.Element:
    tree = ET.parse(path)
    root = tree.getroot()
    if _local(root.tag) != "View":
        raise AssertionError(f"{path.name}: root must be View, got {_local(root.tag)}")
    return root


class OverlayXmlVocabTests(unittest.TestCase):
    def assert_contract(self, path: Path, frame_rate: str) -> None:
        root = _parse(path)
        xml_text = path.read_text(encoding="utf-8")

        timelines = _findall(root, "TimelineLabels")
        self.assertEqual(len(timelines), 2, f"{path.name}: expected exactly 2 TimelineLabels")

        phase, quality = timelines
        self.assertEqual(phase.attrib.get("name"), "videoLabels")
        self.assertEqual(phase.attrib.get("toName"), "video")
        phase_values = tuple(el.attrib.get("value") for el in _findall(phase, "Label"))
        self.assertEqual(phase_values, PHASE_LABELS)

        self.assertEqual(quality.attrib.get("name"), "actionQuality")
        self.assertEqual(quality.attrib.get("toName"), "video")
        quality_values = [el.attrib.get("value") for el in _findall(quality, "Label")]
        self.assertEqual(quality_values, ["质量=0"])

        for old in FORBIDDEN_OLD_LABELS:
            self.assertNotIn(old, phase_values)
            self.assertNotIn(f'value="{old}"', xml_text)

        for name in REMOVED_CONTROL_NAMES:
            self.assertNotIn(f'name="{name}"', xml_text)
        self.assertEqual(_findall(root, "TextArea"), [])
        granularity = [el for el in _findall(root, "Choices") if el.attrib.get("name") == "granularity"]
        self.assertEqual(granularity, [])

        discard = [el for el in _findall(root, "Choices") if el.attrib.get("name") == "discard"]
        self.assertEqual(len(discard), 1, f"{path.name}: discard Choices must remain")
        discard_values = [el.attrib.get("value") for el in _findall(discard[0], "Choice")]
        self.assertEqual(discard_values, ["废弃"])
        self.assertNotIn("废弃", phase_values)
        self.assertNotIn("废弃", quality_values)

        videos = _findall(root, "Video")
        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0].attrib.get("frameRate"), frame_rate)

    def test_single_view_vocab_and_quality_axis(self) -> None:
        self.assert_contract(SINGLE_VIEW, "30.0")

    def test_single_view_rlds_vocab_and_quality_axis(self) -> None:
        self.assert_contract(SINGLE_VIEW_RLDS, "10.0")


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    sys.exit(0 if result.wasSuccessful() else 1)
