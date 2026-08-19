from app.schemas.clients import ClientCreate, ClientUpdate


def test_client_phone_numbers_are_normalized_on_create_and_update() -> None:
    created = ClientCreate(
        business_name="Demo Traders",
        legal_name="Demo Traders",
        gstin="27abcde1234f1z5",
        state="Maharashtra",
        filing_frequency="monthly",
        contact_name="Demo Client",
        whatsapp_phone="91 98765-43210",
    )
    updated = ClientUpdate(whatsapp_phone="91 91234-56789")

    assert created.gstin == "27ABCDE1234F1Z5"
    assert created.whatsapp_phone == "+919876543210"
    assert updated.whatsapp_phone == "+919123456789"
