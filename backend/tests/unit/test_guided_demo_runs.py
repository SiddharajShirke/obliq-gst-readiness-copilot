from app.config import Settings
from app.repositories.memory import DEMO_ADMIN_ID, MemoryStore
from app.services.guided_demo import (
    complete_guided_demo_run,
    list_guided_demo_runs,
    start_guided_demo_run,
)


async def test_guided_demo_runs_are_numbered_and_completed_runs_remain_visible(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        local_upload_dir=tmp_path / "uploads",
        local_export_dir=tmp_path / "exports",
        _env_file=None,
    )
    store = MemoryStore(settings)

    first = await start_guided_demo_run(store, settings, DEMO_ADMIN_ID)
    await store.insert_row(
        "audit_events",
        {
            "firm_id": first["firm_id"],
            "user_id": DEMO_ADMIN_ID,
            "action": "gst_export_pack_generated",
            "entity_type": "application",
            "entity_id": first["session_application_id"],
            "application_id": first["session_application_id"],
        },
    )
    completed = await complete_guided_demo_run(
        store,
        run_id=first["id"],
        firm_id=first["firm_id"],
        user_id=DEMO_ADMIN_ID,
    )
    second = await start_guided_demo_run(store, settings, DEMO_ADMIN_ID)
    history = await list_guided_demo_runs(
        store, firm_id=first["firm_id"], user_id=DEMO_ADMIN_ID
    )

    assert completed["status"] == "completed"
    assert first["run_number"] == 1
    assert first["name"] == "Guided Demo 1"
    assert second["run_number"] == 2
    assert second["name"] == "Guided Demo 2"
    assert [row["status"] for row in history] == ["active", "completed"]
    assert first["session_application_id"] != second["session_application_id"]


async def test_guided_demo_completion_requires_a_successful_export(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        whatsapp_provider="mock",
        local_upload_dir=tmp_path / "uploads",
        local_export_dir=tmp_path / "exports",
        _env_file=None,
    )
    store = MemoryStore(settings)
    run = await start_guided_demo_run(store, settings, DEMO_ADMIN_ID)

    try:
        await complete_guided_demo_run(
            store,
            run_id=run["id"],
            firm_id=run["firm_id"],
            user_id=DEMO_ADMIN_ID,
        )
    except ValueError as exc:
        assert str(exc) == "Guided Demo can complete only after Export Pack generation"
    else:
        raise AssertionError("Completion succeeded without a generated Export Pack")
