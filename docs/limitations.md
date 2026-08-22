# Limitations

- The Vonage Messages API Sandbox is intended for initial functional exploration, not QA/staging or production.
- The OBLIQ walkthrough supports one judge at a time. The judge must send the Sandbox allow-list message; OBLIQ cannot automatically confirm that action.
- The Sandbox is limited to 100 messages per month across channels and one message per second; excess requests may receive HTTP 429.
- Sandbox membership and the 24-hour customer-care window are controlled by Vonage and WhatsApp.
- WhatsApp remains deterministic: `STATUS`, `HELP`, and `CANCEL`; tax/legal questions are escalated.
- Secure browser upload supports private intake and cloned-checklist updates. `Uploaded` means stored safely, while `Awaiting Processing` means no extraction has run.
- Direct WhatsApp media is detected but not downloaded, stored, classified, extracted, or shown as a document.
- WhatsApp tax/legal questions are escalated for CA review and are not answered by RAG or an LLM.
- Cleanup is opportunistic plus a manual command; it removes retained demo-upload objects and metadata, but no scheduler or distributed worker is included.
- The in-process rate limiter is prototype-local and does not coordinate across multiple FastAPI replicas.
- Real delivery requires external Vonage credentials, an allow-listed device, and a public HTTPS callback.

Secure intake validates format signatures and basic structure but is not a malware scanner or content-disarm service. Existing explicit document processing, OCR, AI extraction, document viewers, RAG, validation, reconciliation, reports, and audit functionality remain separate from the Vonage media path.

General prototype limitations remain: no direct GST Portal/ASP/GSP filing, DSC/EVC signing, payment, final ITC decision, enterprise secret manager, malware/content-disarm pipeline, resilient distributed job queue, multi-region operation, external security certification, or real-time statutory deadline synchronization. OCR quality and simplified reconciliation rules continue to require CA review.
