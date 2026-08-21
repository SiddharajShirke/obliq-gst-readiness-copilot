# Phase 1 live WhatsApp walkthrough

1. Start Supabase, FastAPI, Next.js, and ngrok when local.
2. Configure the Vonage Sandbox inbound and status webhooks with the public `PUBLIC_BASE_URL`.
3. Log in to OBLIQ.
4. Create or select any client and GST period.
5. Open the GST workspace and click **Open Live WhatsApp Demo**.
6. Confirm the client and period are application-specific.
7. Scan the common Sandbox join QR and send the join message.
8. Scan the unique START QR and send the START message.
9. Confirm the dashboard becomes active and shows only masked phone digits.
10. Confirm the real checklist arrives in WhatsApp.
11. Send `STATUS`, `HELP`, a tax question, and an unsupported message.
12. Confirm deterministic responses and CA-review escalation.
13. Send an attachment and confirm OBLIQ does not download it or create a document row.
14. Confirm the controlled Phase 1 media response.
15. Confirm status callbacks update the last outbound delivery state.
16. Cancel the session and confirm it can no longer receive workflow replies.
17. Run the cleanup command and confirm expired phone data is anonymized.

If Vonage forwards the Sandbox join phrase to the inbound webhook, OBLIQ
silently acknowledges it after signature validation. It is not stored as a demo
conversation message and does not generate an OBLIQ reply.

This Sandbox walkthrough is intentionally limited to one judge at a time. Do not claim real delivery was verified unless this flow was executed with real Vonage credentials, an allow-listed WhatsApp device, and a public HTTPS webhook.
