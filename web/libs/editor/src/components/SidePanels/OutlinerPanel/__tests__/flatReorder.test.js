/**
 * Unit tests for flat outliner reorder (display order, not ouid / frames).
 */
import { describe, expect, it } from "bun:test";
import { dropPlace, moveId, shouldFlatReorder } from "../flatReorder";

describe("moveId", () => {
  it("inserts drag before drop, including the first row", () => {
    expect(moveId(["static", "grasp", "place"], "place", "static", "before")).toEqual([
      "place",
      "static",
      "grasp",
    ]);
  });

  it("inserts drag after drop", () => {
    expect(moveId(["static", "grasp", "place"], "static", "place", "after")).toEqual([
      "grasp",
      "place",
      "static",
    ]);
  });
});

describe("dropPlace", () => {
  it("treats drop-on-body as insert-before, never nest", () => {
    expect(dropPlace(false, 0, 0)).toBe("before");
    expect(dropPlace(false, 1, 0)).toBe("before");
  });

  it("treats gap above first row as insert-before", () => {
    expect(dropPlace(true, -1, 0)).toBe("before");
    expect(dropPlace(true, 0, 0)).toBe("before");
  });

  it("treats gap below a row as insert-after", () => {
    expect(dropPlace(true, 2, 1)).toBe("after");
  });
});

describe("shouldFlatReorder", () => {
  it("only flattens timeline regions", () => {
    expect(shouldFlatReorder({ type: "timelineregion" }, { type: "timelineregion" })).toBe(true);
    expect(shouldFlatReorder({ type: "rectangleregion" }, { type: "rectangleregion" })).toBe(false);
  });
});
