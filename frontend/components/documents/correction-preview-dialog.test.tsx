import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {CorrectionPreviewDialog} from "./correction-preview-dialog";

describe("correction preview dialog", () => {
  it("shows exact before and after values and requires an explicit decision", () => {
    const html = renderToStaticMarkup(<CorrectionPreviewDialog
      proposal={{
        id: "proposal-1", proposal_type: "ai", status: "proposed",
        provider: "nvidia", model: "small-model", rationale: "Arithmetic review",
        changes: [{record_id: "record-1", field: "taxable_value", before: "900", after: "950", rationale: "Matches source"}],
      }}
      busy={false}
      onApply={() => undefined}
      onReject={() => undefined}
      onClose={() => undefined}
    />);
    expect(html).toContain("CORRECTION CONFIRMATION");
    expect(html).toContain("₹900");
    expect(html).toContain("₹950");
    expect(html).toContain("Nvidia");
    expect(html).toContain("Apply confirmed correction");
    expect(html).toContain("Reject proposal");
  });
});
