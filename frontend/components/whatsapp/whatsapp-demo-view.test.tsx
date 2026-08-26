import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
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
          checklist: [{
            id: "r1",
            label: "Sales Register",
            status: "received",
            upload_status: "uploaded",
            processing_status: "awaiting_processing",
          }],
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
    expect(html).toContain("Vonage Sandbox Connection");
    expect(html).toContain("Start OBLIQ Session");
    expect(html).toContain("Scan the Vonage Sandbox QR");
    expect(html).toContain("Wait until the Sandbox connection is ready");
    expect(html).toContain("Scan the OBLIQ START QR");
    expect(html).toContain("WhatsApp Connected");
    expect(html).toContain("Vonage WhatsApp Sandbox");
    expect(html).toContain("one judge");
    expect(html).toContain("+91 ******3210");
    expect(html).toContain("Sales Register");
    expect(html).toContain("Uploaded");
    expect(html).toContain("Awaiting Processing");
    expect(html.match(/data-qr-scan-surface="true"/g) ?? []).toHaveLength(2);
    expect(html.match(/fill="#0F172A"/g) ?? []).toHaveLength(2);
    expect(html).not.toContain("Reply as the client");
    expect(html).not.toContain("not-rendered");
    expect(html).not.toContain("Twilio");
  });

  it("shows an explicit reconnect action for a retained cancelled session", () => {
    const html = renderToStaticMarkup(React.createElement(WhatsAppDemoView as never, {
      created: {
        session_id: "session-a",
        base_client_name: "Raj Traders",
        gst_period: "April 2026",
        status: "cancelled",
        token_expires_at: "2026-08-19T12:20:00Z",
        session_expires_at: "2026-08-19T14:00:00Z",
        sandbox_sender: "+14155238886",
        sandbox_join_message: "join obliq-demo",
        sandbox_join_whatsapp_url: "https://wa.me/14155238886",
        start_message: "START OBLIQ DEMO A7K2P9DX",
        start_whatsapp_url: "https://wa.me/14155238886",
        dashboard_access_token: "super-secret-dashboard-token",
      },
      status: {
        status: "cancelled",
        connection_status: "waiting",
        masked_phone: null,
        client_name: "Raj Traders",
        gst_period: "April 2026",
        current_step: "documents_received",
        checklist: [],
        last_activity_at: null,
        token_expires_at: "2026-08-19T12:20:00Z",
        session_expires_at: "2026-08-19T14:00:00Z",
        last_outbound_delivery_status: null,
      },
      countdown: "00:00",
      busy: false,
      onCopy: () => undefined,
      onRegenerate: () => undefined,
      onCancel: () => undefined,
      onReconnect: () => undefined,
    }));

    expect(html).toContain("Reconnect WhatsApp");
    expect(html).toContain("same retained checklist and uploads");
  });

  it("shows dynamic recovery guidance when no valid START webhook reaches OBLIQ", () => {
    const html = renderToStaticMarkup(React.createElement(WhatsAppDemoView as never, {
      created: {
        session_id: "session-a",
        base_client_name: "Raj Traders",
        gst_period: "April 2026",
        status: "waiting_for_start",
        token_expires_at: "2026-08-26T12:20:00Z",
        session_expires_at: "2026-08-26T14:00:00Z",
        sandbox_sender: "+14155238886",
        sandbox_join_message: "join obliq-demo",
        sandbox_join_whatsapp_url: "https://wa.me/14155238886",
        start_message: "START OBLIQ DEMO A7K2P9DX",
        start_whatsapp_url: "https://wa.me/14155238886",
        dashboard_access_token: "hidden",
      },
      status: {
        status: "waiting_for_start",
        connection_status: "waiting",
        masked_phone: null,
        client_name: "Raj Traders",
        gst_period: "April 2026",
        current_step: null,
        checklist: [],
        last_activity_at: "2026-08-26T12:00:00Z",
        token_expires_at: "2026-08-26T12:20:00Z",
        session_expires_at: "2026-08-26T14:00:00Z",
        last_outbound_delivery_status: null,
        connection_diagnostic: {
          state: "awaiting_valid_start",
          valid_start_received: false,
          waited_seconds: 45,
          session_created_at: "2026-08-26T12:00:00Z",
          connected_at: null,
          inbound_webhook_url: "https://api.example.com/api/v1/webhooks/vonage/whatsapp",
          status_callback_url: "https://api.example.com/api/v1/webhooks/vonage/status",
        },
        upload_workflow: {
          state: "waiting_for_connection",
          secure_link_created: false,
          received_document_count: 0,
          latest_link_expires_at: null,
        },
      },
      countdown: "19:15",
      busy: false,
      onCopy: () => undefined,
      onRegenerate: () => undefined,
      onCancel: () => undefined,
    }));

    expect(html).toContain("No valid START webhook received");
    expect(html).toContain("Joining the Sandbox does not start the OBLIQ session");
    expect(html).toContain("https://api.example.com/api/v1/webhooks/vonage/whatsapp");
    expect(html).toContain("Messages API Sandbox");
    expect(html).not.toContain("super-secret-dashboard-token");
  });

  it("shows the session-scoped upload workflow state after connection", () => {
    const html = renderToStaticMarkup(React.createElement(WhatsAppDemoView as never, {
      created: {
        session_id: "session-a",
        base_client_name: "Raj Traders",
        gst_period: "April 2026",
        status: "active",
        token_expires_at: "2026-08-26T12:20:00Z",
        session_expires_at: "2026-08-26T14:00:00Z",
        sandbox_sender: "+14155238886",
        sandbox_join_message: "join obliq-demo",
        sandbox_join_whatsapp_url: "https://wa.me/14155238886",
        start_message: "START OBLIQ DEMO A7K2P9DX",
        start_whatsapp_url: "https://wa.me/14155238886",
        dashboard_access_token: "hidden",
      },
      status: {
        status: "active",
        connection_status: "connected",
        masked_phone: "+91 ******3210",
        client_name: "Raj Traders",
        gst_period: "April 2026",
        current_step: null,
        checklist: [],
        last_activity_at: "2026-08-26T12:00:00Z",
        token_expires_at: "2026-08-26T12:20:00Z",
        session_expires_at: "2026-08-26T14:00:00Z",
        last_outbound_delivery_status: null,
        connection_diagnostic: {
          state: "connected",
          valid_start_received: true,
          waited_seconds: 0,
          session_created_at: "2026-08-26T12:00:00Z",
          connected_at: "2026-08-26T12:01:00Z",
          inbound_webhook_url: "https://api.example.com/api/v1/webhooks/vonage/whatsapp",
          status_callback_url: "https://api.example.com/api/v1/webhooks/vonage/status",
        },
        upload_workflow: {
          state: "secure_link_ready",
          secure_link_created: true,
          received_document_count: 0,
          latest_link_expires_at: "2026-08-27T12:01:00Z",
        },
      },
      countdown: "19:15",
      busy: false,
      onCopy: () => undefined,
      onRegenerate: () => undefined,
      onCancel: () => undefined,
    }));

    expect(html).toContain("Secure upload link ready");
    expect(html).toContain("Review and send the prepared request");
  });
});
