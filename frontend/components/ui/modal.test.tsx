import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";
import {Modal} from "./modal";

describe("Modal", () => {
  it("exposes labelled modal semantics and a focusable panel", () => {
    const html = renderToStaticMarkup(<Modal titleId="dialog-title" onClose={vi.fn()} className="max-w-lg"><h2 id="dialog-title">Ready</h2><button>Close</button></Modal>);

    expect(html).toContain("role=\"dialog\"");
    expect(html).toContain("aria-modal=\"true\"");
    expect(html).toContain("aria-labelledby=\"dialog-title\"");
    expect(html).toContain("tabindex=\"-1\"");
  });
});
