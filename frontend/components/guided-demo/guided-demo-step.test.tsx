import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";
import {GuidedDemoStep} from "./guided-demo-step";

vi.mock("@/components/ui/button", async () => import("../ui/button"));

describe("GuidedDemoStep", () => {
  it("presents concise sequential guidance and explicit actions", () => {
    const html = renderToStaticMarkup(<GuidedDemoStep
      instruction={{step: 4, title: "Review Extracted Data", explanation: "Compare structured records.", why: "AI extracts; the CA verifies.", actionLabel: "Review Extractions"}}
      primaryAction={{onClick: vi.fn()}}
      secondaryAction={{label: "Later", onClick: vi.fn()}}
      onDismiss={vi.fn()}
    />);

    expect(html).toContain("STEP 4 OF 6");
    expect(html).toContain("Review Extracted Data");
    expect(html).toContain("Compare structured records.");
    expect(html).toContain("AI extracts; the CA verifies.");
    expect(html).toContain("Review Extractions");
    expect(html).toContain("Dismiss Guided Demo instructions");
  });
});
