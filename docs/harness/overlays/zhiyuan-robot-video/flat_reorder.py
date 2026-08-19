"""Flat outliner reorder. Display order only; does not change ouid or frames."""

from __future__ import annotations


def move_id(ids: list[str], drag_id: str, drop_id: str, place: str) -> list[str]:
    if not ids or not drag_id or not drop_id:
        return list(ids or [])
    next_ids = [item for item in ids if item != drag_id]
    try:
        drop_index = next_ids.index(drop_id)
    except ValueError:
        return next_ids + [drag_id]
    insert_at = drop_index + 1 if place == "after" else drop_index
    next_ids.insert(insert_at, drag_id)
    return next_ids


def drop_place(drop_to_gap: bool, drop_position: int, drop_index: int) -> str:
    if not drop_to_gap:
        return "before"
    adjusted = int(drop_position) - int(drop_index)
    return "before" if adjusted <= 0 else "after"
