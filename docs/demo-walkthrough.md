# Phase 1 + Phase 2 live WhatsApp and secure-upload walkthrough

1. Start Supabase, FastAPI, Next.js, and ngrok when local.
2. Configure the Vonage Sandbox inbound and status webhooks with the public `PUBLIC_BASE_URL`.
3. Log in to OBLIQ.
4. Create or select any client and GST period.
5. Open the GST workspace and click **Open Live WhatsApp Demo**.
6. Confirm the client and period are application-specific.
7. Scan the common Sandbox join QR and send the join message.
8. Scan the unique START QR and send the START message.
9. Confirm the dashboard becomes active and shows only masked phone digits.
10. Return to the GST workspace, confirm the preserved request preview now contains the application/session-specific secure upload link, and press **Send Request**.
11. Confirm the reviewed request and secure upload link arrive in real WhatsApp. Send `STATUS`, `HELP`, a tax question, and an unsupported message.
12. Confirm deterministic responses and CA-review escalation.
13. Open the secure link without signing into OBLIQ and confirm only the selected client, GST period, checklist, accepted formats, and size limit appear.
14. Upload a synthetic Sales Register against the matching checklist category.
15. Confirm the page and live session dashboard show **Uploaded / Awaiting Processing**.
16. Confirm the object exists under the session-scoped path in the private `gst-documents` bucket and the document row has `source = secure_link` and `processing_status = awaiting_processing`.
17. Confirm only the cloned requirement is received; the base application and a second session remain unchanged.
18. Draft a reminder and confirm it lists only the currently missing categories, then send it through the same active session without scanning again.
19. Send a direct WhatsApp attachment and confirm OBLIQ does not download it or create a document row; the response points back to the secure browser link.
20. Confirm status callbacks update the last outbound delivery state.
21. Cancel the session, press **Reconnect WhatsApp**, and confirm a new START token rebinds the same retained clone/checklist/progress without creating a clone.
22. Run cleanup and confirm expired phone data is anonymized; after 24-hour deletion, reconnect creates a normal new isolated session.

If Vonage forwards the Sandbox join phrase to the inbound webhook, OBLIQ
silently acknowledges it after signature validation. It is not stored as a demo
conversation message and does not generate an OBLIQ reply.

This Sandbox walkthrough is intentionally limited to one judge at a time. Use synthetic files only. Do not claim real delivery or Storage verification unless this flow was executed with real Vonage credentials, an allow-listed WhatsApp device, a public HTTPS webhook, and the configured Supabase project.
