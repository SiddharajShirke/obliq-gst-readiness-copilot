import { describe, expect, it } from "vitest";
import { formatCurrency, formatStatus, statusTone } from "./format";

describe("format helpers", () => {
  it("formats INR using Indian digit grouping", () => {
    expect(formatCurrency(1845000)).toContain("18,45,000");
  });

  it("turns workflow keys into readable labels", () => {
    expect(formatStatus("ready_for_ca_review")).toBe("Ready for CA Review");
  });

  it("maps warning states to the warning tone", () => {
    expect(statusTone("partially_received")).toBe("warning");
  });
});
