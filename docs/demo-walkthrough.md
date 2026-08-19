# Guided Demo Walkthrough

## Goal

Show one continuous story: CA-approved document collection → missing-document reminder → structured extraction → validation → GSTR-2B reconciliation → cited explanation → readiness export.

## Steps

1. Open `/auth/login` and choose **Partner**.
2. Click **Reset demo** on the dashboard to restore the clean guided state.
3. Open **Raj Traders** and its **April 2026** GST application.
4. Click **Draft request**.
5. Read or edit the message, then click **Approve & send**.
6. Open **Open client demo** in a new tab.
7. Choose Raj Traders.
8. Use built-in synthetic samples to send Sales Register, Sales Invoices, Purchase Invoices and GSTR-2B. Leave Purchase Register missing.
9. Return to the CA workspace. The checklist remains 4/5 and Purchase Register is missing.
10. Click **Draft reminder**, review it, then approve and send.
11. Return to the client tab and send the built-in Purchase Register sample.
12. Open **Documents & Extraction**. Select a file, compare its original and JSON, edit one value if desired, and approve it.
13. Add `Purchase_Invoice_Arithmetic_Mismatch.pdf`, `Purchase_Invoice_Wrong_Period.pdf`, and duplicate samples from the local demo folder if running locally.
14. Open **Validation** and run all checks.
15. Open **GSTR-2B Reconciliation** and run matching.
16. Open **RAG Assistant** and ask “What does a GSTR-2B mismatch mean?”
17. Confirm that the response displays a source.
18. Return to Overview and export the readiness pack.
19. Open Audit Trail to show the sequence of actions.

## What to emphasize

- WhatsApp is provider-neutral: hosted mock vs optional local Meta.
- LLMs do not calculate tax or control authorization.
- Parsers and deterministic checks are used before AI.
- The CA reviews extracted fields and outbound communication.
- Client facts come from PostgreSQL; RAG provides sourced explanation.
