from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_rag_security_definer_functions_validate_requested_firm() -> None:
    sql = (ROOT / "supabase" / "migrations" / "202608180003_rag_search_functions.sql").read_text(encoding="utf-8")

    assert sql.count("auth.role() = 'service_role' or public.user_has_firm_access(user_firm_id)") == 2
