from app.config import Settings
from app.repositories.memory import MemoryStore
from app.services.onboarding import bootstrap_user_workspace


async def test_workspace_bootstrap_is_idempotent_and_creates_one_demo_template(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        local_upload_dir=tmp_path / "uploads",
        local_export_dir=tmp_path / "exports",
        _env_file=None,
    )
    store = MemoryStore(settings)
    identity = {
        "id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
        "email": "new.ca@example.com",
        "full_name": "New CA",
    }

    first = await bootstrap_user_workspace(store, identity)
    second = await bootstrap_user_workspace(store, identity)

    assert first == second
    memberships = await store.list_rows("firm_members", {"user_id": identity["id"]})
    templates = await store.list_rows(
        "clients",
        {"firm_id": first["firm_id"], "demo_scenario": "guided_demo_template"},
    )
    applications = await store.list_rows(
        "applications", {"client_id": first["demo_client_id"]}
    )
    requirements = await store.list_rows(
        "document_requirements", {"application_id": first["demo_application_id"]}
    )

    assert len(memberships) == 1
    assert memberships[0]["role"] == "firm_admin"
    assert len(templates) == 1
    assert templates[0]["business_name"] == "Raj Traders"
    assert len(applications) == 1
    assert len(requirements) == 6
    assert {row["status"] for row in requirements} == {"missing"}


async def test_workspace_allows_unlimited_normal_clients_after_bootstrap(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        local_upload_dir=tmp_path / "uploads",
        local_export_dir=tmp_path / "exports",
        _env_file=None,
    )
    store = MemoryStore(settings)
    identity = {
        "id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "email": "growing.ca@example.com",
        "full_name": "Growing CA",
    }
    workspace = await bootstrap_user_workspace(store, identity)

    for index in range(25):
        await store.insert_row(
            "clients",
            {
                "firm_id": workspace["firm_id"],
                "business_name": f"Client {index + 1}",
                "legal_name": f"Client {index + 1} Private Limited",
                "gstin": f"27ABCDE{index:04d}F1Z5",
                "state": "Maharashtra",
                "business_type": "business",
                "filing_frequency": "monthly",
                "contact_name": "Client Contact",
                "whatsapp_phone": f"+91990000{index:04d}",
                "preferred_language": "English",
                "whatsapp_consent": False,
                "demo_scenario": None,
            },
        )

    clients = await store.list_rows("clients", {"firm_id": workspace["firm_id"]})
    assert len(clients) == 26
    assert sum(row.get("demo_scenario") == "guided_demo_template" for row in clients) == 1
