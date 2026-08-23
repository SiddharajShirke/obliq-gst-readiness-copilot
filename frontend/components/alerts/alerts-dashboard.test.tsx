import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {AlertsDashboard} from "./alerts-dashboard";

describe("Alerts Dashboard", () => {
  it("shows exact evidence, AI assistance, and its review disclaimer", () => {
    const html = renderToStaticMarkup(<AlertsDashboard/>);
    expect(html).toContain("GST review alerts");
    expect(html).toContain("Validation");
    expect(html).toContain("Reconciliation");
    expect(html).toContain("Exact Books vs GSTR-2B evidence");
    expect(html).toContain("AI Assistance");
    expect(html).toContain("Final GST and ITC treatment remains subject to CA verification");
    expect(html).toContain("--obliq-surface-raised");
    expect(html).not.toContain("--obliq-soft");
  });
});
