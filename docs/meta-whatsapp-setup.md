# Meta WhatsApp Cloud API — Local Test Setup

## What the numbers mean

- **Meta test business number:** controlled by Cloud API and acts as sender.
- **Reviewer’s verified test recipient:** normal WhatsApp account that receives messages.
- Nobody logs in to the Meta test business number through WhatsApp Web.

## Outbound test

1. Create a Meta developer application.
2. Add the WhatsApp product.
3. Copy the Phone Number ID, WABA ID and test access token.
4. Add and verify your normal WhatsApp number as a test recipient.
5. Set `.env`:

```env
WHATSAPP_PROVIDER=meta
ALLOW_LOCAL_CREDENTIAL_SETUP=true
META_ACCESS_TOKEN=...
META_PHONE_NUMBER_ID=...
META_WABA_ID=...
META_APP_SECRET=...
META_WEBHOOK_VERIFY_TOKEN=obliq-local-verify-token
META_GRAPH_API_VERSION=v26.0
META_TEST_RECIPIENT_NUMBER=+91...
```

6. Restart FastAPI.
7. Use **Dashboard → WhatsApp → Send test message**, or run:

```bash
python scripts/verify_meta_setup.py
```

A recipient number alone is not sufficient; it must be configured in the reviewer’s Meta developer test setup.

## Inbound webhooks with ngrok

Meta cannot call `localhost`. Expose FastAPI:

```bash
ngrok http 8000
```

Set:

```env
PUBLIC_WEBHOOK_BASE_URL=https://YOUR-NGROK-DOMAIN
```

Restart FastAPI and configure the Meta callback URL shown in the OBLIQ integration page:

```text
https://YOUR-NGROK-DOMAIN/api/v1/webhooks/whatsapp
```

Use the same verify token as `META_WEBHOOK_VERIFY_TOKEN`, subscribe to message events, then send text or media from your verified recipient account.

## Templates and customer-service window

Depending on the current Meta account state and messaging context, a business-initiated message may require an approved utility template. The adapter supports template names through environment variables; the simple prototype request flow sends text by default. Adjust the provider call to template mode for your approved Meta setup.

## Local credential form

When `ALLOW_LOCAL_CREDENTIAL_SETUP=true`, the dashboard can save credentials to `.runtime/meta_credentials.json`. That file is gitignored and chmod-restricted, but this remains a prototype convenience—not a production secrets design.
