import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {RagAssistantDrawer} from "./assistant-panel";

describe("application RAG assistant drawer", () => {
  it("is anchored to the current application and shows contextual questions", () => {
    const html = renderToStaticMarkup(
      <RagAssistantDrawer
        applicationId="session-app-42"
        clientName="Raj Traders"
        period="August 2026"
        missingCount={2}
        hasExtraction
        hasReconciliation
        open
      />,
    );

    expect(html).toContain('data-application-id="session-app-42"');
    expect(html).toContain("Ask OBLIQ");
    expect(html).toContain("Raj Traders");
    expect(html).toContain("August 2026");
    expect(html).toContain("Which client documents are still missing?");
    expect(html).toContain("Summarize the Purchase Register.");
    expect(html).toContain("Explain the GSTR-2B mismatches.");
    expect(html).toContain("Sources appear here with document, page, sheet, or row provenance");
  });
});
