import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {FindingsPanel} from "./findings-panel";

describe("validation findings panel", () => {
  it("invites row-level inspection without exposing raw JSON", () => {
    const html = renderToStaticMarkup(
      <FindingsPanel applicationId="app-1" onChanged={() => undefined}/>,
    );

    expect(html).toContain("Validation Portfolio");
    expect(html).toContain("Portfolio");
    expect(html).toContain("Table");
    expect(html).toContain("Manual corrections and AI recommendations always require CA confirmation");
    expect(html).toContain("Select All");
    expect(html).toContain("Select all visible validation findings");
    expect(html).not.toContain("JSON.stringify");
  });
});
