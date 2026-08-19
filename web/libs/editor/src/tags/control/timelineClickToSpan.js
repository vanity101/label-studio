/** Click-to-span math for TimelineLabels. Frames are 1-based. */

export const DISCARD_LABEL = "废弃";
export const DISCARD_FROM_NAME = "discard";

function toFrame(value, fallback = 1) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 1) return fallback;
  return Math.floor(number);
}

/**
 * @param {number | null | undefined} previousEnd end frame of the last created span
 * @param {number | null | undefined} playhead current video frame
 * @returns {{ start: number, end: number }}
 */
export function nextClickSpan(previousEnd, playhead) {
  const head = toFrame(playhead);
  if (previousEnd == null) {
    return { start: 1, end: head };
  }
  const prev = toFrame(previousEnd);
  if (head > prev) {
    return { start: prev + 1, end: head };
  }
  return { start: head, end: prev };
}

/**
 * @param {Array<{ type?: string, ouid?: number, ranges?: Array<{ end?: number }> }>} regions
 */
export function lastCreatedTimelineRegion(regions) {
  const list = (regions || []).filter((region) => region?.type === "timelineregion");
  if (!list.length) return null;
  return [...list].sort((a, b) => (a.ouid ?? 0) - (b.ouid ?? 0)).at(-1);
}

function cleanedName(value) {
  return String(value ?? "").replace(/@.*/, "");
}

function tagMatchesName(tag, name) {
  if (!tag || !name) return false;
  return tag.name === name || cleanedName(tag.name) === name;
}

/**
 * Resolve a tag by XML `name`. `annotation.names` may be a JS Map or an MST map,
 * and keys may be `name` or `name@annotationId`.
 */
export function resolveNamedTag(annotation, name) {
  if (!annotation || !name) return null;
  const map = annotation.names;
  if (typeof map?.get === "function") {
    const direct = map.get(name);
    if (direct) return direct;
  }
  const values = typeof map?.values === "function" ? Array.from(map.values()) : [];
  const fromMap = values.find((tag) => tagMatchesName(tag, name));
  if (fromMap) return fromMap;
  const objects = annotation.objects ?? [];
  return objects.find((tag) => tagMatchesName(tag, name)) ?? null;
}

export function isDiscardValues(values) {
  return Array.isArray(values) && values.includes(DISCARD_LABEL);
}

export function canCreateSpan(discarded) {
  return !discarded;
}

export function phaseLabelValues(labels) {
  return (labels || []).map((item) => item?.value).filter((value) => value && value !== DISCARD_LABEL);
}

/**
 * Switch a timeline region's label without changing start/end.
 * @returns {boolean} whether the name was applied
 */
export function applyPhaseLabel(region, control, value) {
  if (!region || !control || !value) return false;
  if (value === DISCARD_LABEL) return false;
  if (region.isReadOnly?.() || region.object?.isDiscarded) return false;
  const current = region.labeling?.mainValue?.[0];
  if (current === value) return true;
  const label = control.findLabel?.(value);
  if (!label) return false;
  control.unselectAll?.();
  label.setSelected?.(true);
  region.setValue(control);
  control.unselectAll?.();
  return true;
}
