import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {WhatsAppRuntimeStatus} from "./whatsapp-runtime-status";

describe("Vonage runtime status", () => {
  it("renders operational URLs and no editable secrets", () => {
    const html = renderToStaticMarkup(<WhatsAppRuntimeStatus status={{
      provider: "Vonage Messages API Sandbox",
      configuration: "Ready",
      sandbox_sender: "+14155238886",
      inbound_webhook_url: "https://api.example.com/api/v1/webhooks/vonage/whatsapp",
      status_callback_url: "https://api.example.com/api/v1/webhooks/vonage/status",
      public_base_url: "https://api.example.com",
      last_webhook_time: null,
      last_successful_message: null,
    }} onCopy={() => undefined}/>);

    expect(html).toContain("Vonage Messages API Sandbox");
    expect(html).toContain("/webhooks/vonage/whatsapp");
    expect(html).toContain("/webhooks/vonage/status");
    expect(html).not.toContain("API Secret");
    expect(html).not.toContain("Signature Secret");
    expect(html).not.toContain("Twilio");
    expect(html).not.toContain("<input");
  });
});
