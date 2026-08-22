# Vonage Messages API WhatsApp Sandbox setup

## Sandbox configuration

1. Sign in to the Vonage API Dashboard and open **Messages API Sandbox**.
2. Select the API key used for the Sandbox and add the WhatsApp channel.
3. Copy the API key, API secret, webhook signature secret, Sandbox sender, and exact WhatsApp allow-list message into the backend environment. Never put these values in `NEXT_PUBLIC_*` variables.
4. Configure the Sandbox **Inbound webhook** as an HTTP `POST`:

```text
{PUBLIC_BASE_URL}/api/v1/webhooks/vonage/whatsapp
```

5. Configure the Sandbox **Status webhook** as an HTTP `POST`:

```text
{PUBLIC_BASE_URL}/api/v1/webhooks/vonage/status
```

6. Ensure signed webhooks are enabled. OBLIQ rejects unsigned, malformed, stale, API-key-mismatched, or payload-tampered callbacks before any database write.

The active outbound Sandbox endpoint is:

```text
POST https://messages-sandbox.nexmo.com/v1/messages
```

OBLIQ sends normal `message_type=text` JSON within the user-initiated 24-hour customer-care window. It does not use templates in this phase.

## Required backend environment

```env
WHATSAPP_PROVIDER=vonage
VONAGE_API_KEY=
VONAGE_API_SECRET=
VONAGE_SIGNATURE_SECRET=
VONAGE_WHATSAPP_FROM=
VONAGE_SANDBOX_JOIN_MESSAGE=
VONAGE_MESSAGES_BASE_URL=https://messages-sandbox.nexmo.com
PUBLIC_BASE_URL=https://your-public-backend-url
```

Use the exact sender and allow-list phrase displayed by your Vonage Sandbox. The application strips `whatsapp:` and punctuation when it builds `wa.me` links and provider recipients.

## Local ngrok

Run:

```powershell
ngrok http 8000
```

Set:

```env
PUBLIC_BASE_URL=https://generated-domain.ngrok-free.app
```

Restart FastAPI after changing the public URL, then paste the two webhook URLs above into the Vonage Sandbox dashboard. Keep ngrok running while testing.

## Judge onboarding and manual check

The Phase 1 walkthrough supports one judge at a time:

1. Open an application-specific live demo page.
2. Scan the common Vonage Sandbox QR and send the pre-filled allow-list message.
3. Scan the unique OBLIQ START QR and send the START message.
4. Confirm the signed inbound webhook returns HTTP 200 and the judge receives the checklist.
5. Send `STATUS` and `HELP`; confirm each response and its status callback.
6. Open the secure browser link included in the welcome message and upload one synthetic GST file.
7. Confirm the private Storage object, `secure_link` document row, cloned checklist update, and `awaiting_processing` status.
8. Send a direct WhatsApp attachment; confirm OBLIQ does not download it, creates no document row, and points back to the secure link.

Vonage may forward the configured allow-list message to the inbound webhook in
addition to sending its own Sandbox confirmation. OBLIQ validates that webhook
and silently acknowledges an exact, case-insensitive match without storing it or
sending a second application reply.

The Sandbox is free for exploration but limited to 100 messages per month across supported channels and one message per second. It is not a production or sustained QA environment. A production deployment requires a proper WhatsApp Business Account and production Vonage Messages API setup.

Phase 1 implements real text transport, inbound webhook validation, isolated OBLIQ sessions, and delivery-status tracking. Phase 2 adds private Supabase Storage intake through a session-bound browser link and live cloned-checklist status. Direct WhatsApp media download, OCR, AI extraction, checklist mutation from attachments, and document-content viewer changes remain deferred.
