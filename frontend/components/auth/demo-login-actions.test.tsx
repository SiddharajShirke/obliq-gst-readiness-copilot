import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";

import {DemoLoginActions} from "./demo-login-actions";

describe("DemoLoginActions", () => {
  it("renders no fake-token login controls in Supabase mode", () => {
    const html = renderToStaticMarkup(
      <DemoLoginActions enabled={false} busy={false} onLogin={vi.fn()}/>,
    );

    expect(html).not.toContain("Partner");
    expect(html).not.toContain("Preparer");
    expect(html).not.toContain("Reviewer");
  });

  it("keeps role controls for intentional MemoryStore demo mode", () => {
    const html = renderToStaticMarkup(
      <DemoLoginActions enabled busy={false} onLogin={vi.fn()}/>,
    );

    expect(html).toContain("Partner");
    expect(html).toContain("Preparer");
    expect(html).toContain("Reviewer");
  });
});
