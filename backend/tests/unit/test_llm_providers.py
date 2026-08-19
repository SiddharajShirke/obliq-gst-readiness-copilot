import base64

from app.services.llm.providers import build_gemini_document_payload


def test_gemini_document_payload_embeds_file_bytes_and_json_contract() -> None:
    payload = build_gemini_document_payload(
        system_prompt="Extract GST fields",
        user_prompt="Document type: purchase_invoice",
        content=b"fake-image-bytes",
        mime_type="image/jpeg",
    )

    parts = payload["contents"][0]["parts"]
    assert parts[0] == {"text": "Document type: purchase_invoice"}
    assert parts[1]["inlineData"]["mimeType"] == "image/jpeg"
    assert base64.b64decode(parts[1]["inlineData"]["data"]) == b"fake-image-bytes"
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
