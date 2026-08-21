import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {LiveWhatsAppDemoLink} from "./live-whatsapp-demo-link";

describe("live WhatsApp application link", () => {
  it("targets the selected dynamic GST application", () => {
    const html = renderToStaticMarkup(<LiveWhatsAppDemoLink applicationId="app-new-2026"/>);

    expect(html).toContain("/dashboard/applications/app-new-2026/whatsapp-demo");
    expect(html).toContain("Open Live WhatsApp Demo");
  });
});
