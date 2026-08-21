import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { WhatsAppDemoView } from "./whatsapp-demo-view";

describe("live WhatsApp demo view", () => {
  it("renders both real QR actions and live session data without a chat simulator", () => {
    const html = renderToStaticMarkup(
      <WhatsAppDemoView
        created={{
          session_id: "session-a",
          base_client_name: "Raj Traders",
          gst_period: "July 2026",
          status: "waiting_for_start",
          token_expires_at: "2026-08-19T12:20:00Z",
          session_expires_at: "2026-08-19T14:00:00Z",
          sandbox_sender: "+14155238886",
          sandbox_join_message: "join obliq-demo",
          sandbox_join_whatsapp_url: "https://wa.me/14155238886?text=join%20obliq-demo",
          start_message: "START OBLIQ DEMO A7K2P9DX",
          start_whatsapp_url: "https://wa.me/14155238886?text=START%20OBLIQ%20DEMO%20A7K2P9DX",
          dashboard_access_token: "not-rendered",
        }}
        status={{
          status: "active",
          connection_status: "connected",
          masked_phone: "+91 ******3210",
          client_name: "Raj Traders",
          gst_period: "July 2026",
          current_step: "checklist_sent",
          checklist: [{id: "r1", label: "Sales Register", status: "missing"}],
          last_activity_at: "2026-08-19T12:05:00Z",
          token_expires_at: "2026-08-19T12:20:00Z",
          session_expires_at: "2026-08-19T14:00:00Z",
          last_outbound_delivery_status: "delivered",
        }}
        countdown="12:34"
        busy={false}
        onCopy={() => undefined}
        onRegenerate={() => undefined}
        onCancel={() => undefined}
      />,
    );

    expect(html).toContain("Step 1: Join the Sandbox");
    expect(html).toContain("Step 2: Start the OBLIQ session");
    expect(html).toContain("Vonage WhatsApp Sandbox");
    expect(html).toContain("one judge");
    expect(html).toContain("+91 ******3210");
    expect(html).toContain("Sales Register");
    expect(html).not.toContain("Reply as the client");
    expect(html).not.toContain("not-rendered");
    expect(html).not.toContain("Twilio");
  });
});
