from app.services.whatsapp.meta import parse_webhook_payload


def test_parse_webhook_payload_returns_message_and_status_events() -> None:
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "phone-id"},
                    "messages": [{
                        "from": "919800000001",
                        "id": "wamid.inbound",
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": "Uploading now"}
                    }],
                    "statuses": [{
                        "id": "wamid.outbound",
                        "status": "delivered",
                        "timestamp": "1700000001",
                        "recipient_id": "919800000001"
                    }]
                }
            }]
        }]
    }

    events = parse_webhook_payload(payload)

    assert [event.kind for event in events] == ["message", "status"]
    assert events[0].sender_phone == "+919800000001"
    assert events[0].text == "Uploading now"
    assert events[1].status == "delivered"
