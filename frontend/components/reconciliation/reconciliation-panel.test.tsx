import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {ReconciliationPanel} from "./reconciliation-panel";

describe("Phase 3 reconciliation panel", () => {
  it("shows explicit GSTR-2B upload, start, evidence, and CA actions", () => {
    const html = renderToStaticMarkup(<ReconciliationPanel applicationId="app-1" onChanged={() => undefined}/>);
    expect(html).toContain("Upload GSTR-2B");
    expect(html).toContain("Start Reconciliation");
    expect(html).toContain("Exact Matches");
    expect(html).toContain("Raise Alert");
    expect(html).toContain("Select any finding to compare evidence and understand the outcome");
    expect(html).not.toContain("JSON.stringify");
  });
});
