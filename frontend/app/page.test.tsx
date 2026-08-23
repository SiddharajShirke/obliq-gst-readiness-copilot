import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";
import HomePage from "./page";

vi.mock("@/components/landing/navbar", async () => import("../components/landing/navbar"));
vi.mock("@/components/landing/dashboard-preview", async () => import("../components/landing/dashboard-preview"));
vi.mock("@/components/landing/feature-section", async () => import("../components/landing/feature-section"));
vi.mock("@/components/ui/theme-toggle", () => ({ThemeToggle: () => <button>Theme</button>}));

describe("current Phase 1-4 landing page", () => {
  it("presents concise authenticated product entry without obsolete demo shortcuts", () => {
    const html = renderToStaticMarkup(<HomePage/>);

    expect(html).toContain("Automate GST. Review Confidently.");
    expect(html).toContain("Collect, extract, validate, reconcile and prepare GST work in one workspace.");
    expect(html).toContain("Sign in");
    expect(html).not.toMatch(/Open (?:live )?demo/i);
    expect(html).not.toContain("Run guided demo");
  });

  it("describes the implemented Phase 1-4 workflow without obsolete checklist data", () => {
    const html = renderToStaticMarkup(<HomePage/>);

    for (const capability of [
      "Secure Collection",
      "AI Extraction",
      "CA Validation",
      "GSTR-2B Reconciliation",
      "RAG Assistant",
      "Export Pack",
    ]) {
      expect(html).toContain(capability);
    }
    expect(html).toContain("Request");
    expect(html).toContain("Collect");
    expect(html).toContain("Export");
    expect(html).not.toContain("4 / 5");
    expect(html).not.toContain("150 invoices compared");
  });

  it("presents the product journey as an accessible animated brand experience", () => {
    const html = renderToStaticMarkup(<HomePage/>);

    expect(html).toContain('aria-label="OBLIQ GST readiness workflow"');
    expect(html).toContain("landing-hero-grid");
    expect(html).toContain("landing-reveal");
    expect(html).toContain("Private Supabase Storage");
    expect(html).toContain("Deterministic reconciliation");
    expect(html).toContain("Application-scoped RAG");
  });
});
