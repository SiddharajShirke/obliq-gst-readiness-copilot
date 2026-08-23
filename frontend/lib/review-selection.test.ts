import {describe, expect, it} from "vitest";
import {
  selectAllVisible,
  selectionState,
  trimSelectionToVisible,
} from "./review-selection";

describe("filter-aware review selection", () => {
  it("selects only visible eligible IDs and can deselect them", () => {
    expect(selectAllVisible(new Set(["hidden"]), ["visible-1", "visible-2"], true)).toEqual(
      new Set(["hidden", "visible-1", "visible-2"]),
    );
    expect(
      selectAllVisible(new Set(["hidden", "visible-1", "visible-2"]), ["visible-1", "visible-2"], false),
    ).toEqual(new Set(["hidden"]));
  });

  it("reports checked and indeterminate state for visible records", () => {
    expect(selectionState(new Set(["one"]), ["one", "two"])).toEqual({
      checked: false,
      indeterminate: true,
      selectedVisibleCount: 1,
    });
    expect(selectionState(new Set(["one", "two"]), ["one", "two"])).toEqual({
      checked: true,
      indeterminate: false,
      selectedVisibleCount: 2,
    });
  });

  it("removes hidden IDs when a category or filter changes", () => {
    expect(trimSelectionToVisible(new Set(["visible", "hidden"]), ["visible"])).toEqual(
      new Set(["visible"]),
    );
  });
});
