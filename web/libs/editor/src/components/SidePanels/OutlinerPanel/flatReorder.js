/** Flat outliner reorder. Display order only; does not change ouid or frames. */

export function moveId(ids, dragId, dropId, place) {
  if (!Array.isArray(ids) || !dragId || !dropId) return Array.isArray(ids) ? [...ids] : [];
  const next = ids.filter((id) => id !== dragId);
  const dropIndex = next.indexOf(dropId);
  if (dropIndex < 0) {
    next.push(dragId);
    return next;
  }
  const insertAt = place === "after" ? dropIndex + 1 : dropIndex;
  next.splice(insertAt, 0, dragId);
  return next;
}

/**
 * Map rc-tree drop info to insert-before / insert-after.
 * Dropping onto a row body is insert-before (sibling swap), never nest.
 */
export function dropPlace(dropToGap, dropPosition, dropIndex) {
  if (!dropToGap) return "before";
  const adjusted = Number(dropPosition) - Number(dropIndex);
  return adjusted <= 0 ? "before" : "after";
}

export function shouldFlatReorder(dragReg, dropReg) {
  return dragReg?.type === "timelineregion" && dropReg?.type === "timelineregion";
}
