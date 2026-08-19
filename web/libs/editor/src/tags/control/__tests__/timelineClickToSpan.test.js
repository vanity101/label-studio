/**
 * Unit tests for click-to-span math (TimelineLabels click creates a range).
 */
import { describe, expect, it, mock } from "bun:test";
import {
  applyPhaseLabel,
  canCreateSpan,
  DISCARD_LABEL,
  isDiscardValues,
  lastCreatedTimelineRegion,
  nextClickSpan,
  phaseLabelValues,
  resolveNamedTag,
} from "../timelineClickToSpan";

describe("nextClickSpan", () => {
  it("first label uses frame 1 through playhead", () => {
    expect(nextClickSpan(null, 17)).toEqual({ start: 1, end: 17 });
    expect(nextClickSpan(undefined, 1)).toEqual({ start: 1, end: 1 });
  });

  it("later label continues from previous end + 1 when playhead is later", () => {
    expect(nextClickSpan(20, 40)).toEqual({ start: 21, end: 40 });
    expect(nextClickSpan(20, 21)).toEqual({ start: 21, end: 21 });
  });

  it("allows overlap when playhead is at or before previous end", () => {
    expect(nextClickSpan(20, 10)).toEqual({ start: 10, end: 20 });
    expect(nextClickSpan(20, 20)).toEqual({ start: 20, end: 20 });
  });

  it("treats invalid playhead as frame 1", () => {
    expect(nextClickSpan(null, 0)).toEqual({ start: 1, end: 1 });
    expect(nextClickSpan(null, "x")).toEqual({ start: 1, end: 1 });
  });
});

describe("lastCreatedTimelineRegion", () => {
  it("picks the last created timeline region by ouid, not start frame", () => {
    const last = lastCreatedTimelineRegion([
      { type: "timelineregion", ouid: 2, ranges: [{ start: 50, end: 60 }] },
      { type: "timelineregion", ouid: 1, ranges: [{ start: 1, end: 10 }] },
    ]);
    expect(last.ouid).toBe(2);
    expect(last.ranges[0].end).toBe(60);
  });

  it("ignores non-timeline regions", () => {
    expect(lastCreatedTimelineRegion([{ type: "rectangleregion", ouid: 9 }])).toBeNull();
  });
});

describe("resolveNamedTag", () => {
  it("finds a tag when Map keys are name@annotationId", () => {
    const discard = { name: "discard@12", type: "choices" };
    const names = new Map([["discard@12", discard]]);
    expect(resolveNamedTag({ names, objects: [] }, "discard")).toBe(discard);
  });

  it("falls back to objects when names.get misses", () => {
    const video = { name: "video", type: "video" };
    expect(resolveNamedTag({ names: new Map(), objects: [video] }, "video")).toBe(video);
  });
});

describe("discard helpers", () => {
  it("recognizes 废弃 as a whole-video mark, not a span label", () => {
    expect(DISCARD_LABEL).toBe("废弃");
    expect(isDiscardValues(["废弃"])).toBe(true);
    expect(isDiscardValues(["Static"])).toBe(false);
    expect(canCreateSpan(true)).toBe(false);
    expect(canCreateSpan(false)).toBe(true);
  });

  it("filters 废弃 out of phase label dropdown options", () => {
    expect(phaseLabelValues([{ value: "Static" }, { value: "废弃" }, { value: "grasp" }])).toEqual([
      "Static",
      "grasp",
    ]);
  });
});

describe("applyPhaseLabel", () => {
  it("switches the label via the control and does not run when discarded", () => {
    const setValue = mock();
    const unselectAll = mock();
    const setSelected = mock();
    const region = {
      labeling: { mainValue: ["Static"] },
      setValue,
      isReadOnly: () => false,
      object: { isDiscarded: false },
    };
    const control = {
      findLabel: (value) => (value === "grasp" ? { setSelected } : null),
      unselectAll,
    };

    expect(applyPhaseLabel(region, control, "grasp")).toBe(true);
    expect(setSelected).toHaveBeenCalledWith(true);
    expect(setValue).toHaveBeenCalledWith(control);
    expect(unselectAll).toHaveBeenCalled();

    region.object.isDiscarded = true;
    expect(applyPhaseLabel(region, control, "Place")).toBe(false);
  });
});
