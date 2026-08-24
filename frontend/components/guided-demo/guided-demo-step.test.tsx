import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";
import {GuidedDemoStep} from "./guided-demo-step";

vi.mock("@/components/ui/button", async () => import("../ui/button"));

describe("GuidedDemoStep", () => {
  it("presents concise sequential guidance and explicit actions", () => {
    const html = renderToStaticMarkup(<GuidedDemoStep
      instruction={{
        step: 4,
        title: "Review Extracted Data",
        status: "in_progress",
        objective: "Verify every normalized GST record against its source.",
        explanation: "Compare structured records.",
        tasks: ["Open one category.", "Inspect the original and extracted values.", "Approve, edit, or reject the record."],
        why: "AI extracts; the CA verifies.",
        completeWhen: "All 24 eligible records are reviewed.",
        next: "Validation starts from approved records.",
        progress: "12 of 24 records reviewed",
        actionKey: "review_extractions",
        actionLabel: "Review Extractions",
      }}
      primaryAction={{onClick: vi.fn()}}
      secondaryAction={{label: "Later", onClick: vi.fn()}}
      onDismiss={vi.fn()}
    />);

    expect(html).toContain("STEP 4 OF 6");
    expect(html).toContain("Review Extracted Data");
    expect(html).toContain("CURRENT OBJECTIVE");
    expect(html).toContain("Verify every normalized GST record against its source.");
    expect(html).toContain("DO THIS NEXT");
    expect(html).toContain("Open one category.");
    expect(html).toContain("Inspect the original and extracted values.");
    expect(html).toContain("AI extracts; the CA verifies.");
    expect(html).toContain("COMPLETE WHEN");
    expect(html).toContain("All 24 eligible records are reviewed.");
    expect(html).toContain("WHAT HAPPENS NEXT");
    expect(html).toContain("Validation starts from approved records.");
    expect(html).toContain("12 of 24 records reviewed");
    expect(html).toContain("Available anytime");
    expect(html).toContain("RAG Assistant");
    expect(html).toContain("Audit Trail");
    expect(html).toContain("Review Extractions");
    expect(html).toContain("Dismiss Guided Demo instructions");
  });
});
