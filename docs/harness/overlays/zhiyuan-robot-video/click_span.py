"""Click-to-span math. Frames are 1-based. No Label Studio import."""

from __future__ import annotations

DISCARD_LABEL = "废弃"
DISCARD_FROM_NAME = "discard"


def _frame(value, default: int = 1) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number >= 1 else default


def next_click_span(previous_end, playhead) -> tuple[int, int]:
    """Return (start, end) for a click on a phase label at playhead."""
    head = _frame(playhead)
    if previous_end is None:
        return 1, head
    prev = _frame(previous_end)
    if head > prev:
        return prev + 1, head
    return head, prev


def last_created_end(regions: list[dict]) -> int | None:
    """Last created timeline region by ouid / creation order, then its end frame."""
    timeline = [item for item in regions if item.get("type") == "timelineregion"]
    if not timeline:
        return None
    timeline.sort(key=lambda item: item.get("ouid", 0))
    last = timeline[-1]
    ranges = last.get("ranges") or []
    if not ranges:
        return None
    end = ranges[0].get("end")
    return None if end is None else int(end)


def is_discard_values(values) -> bool:
    return isinstance(values, list) and DISCARD_LABEL in values


def can_create_span(discarded: bool) -> bool:
    return not discarded
