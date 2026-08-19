from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = spec_from_file_location("generate_demo_documents", ROOT / "scripts" / "generate_demo_documents.py")
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sync_frontend_demo_documents_mirrors_generated_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "invoice.pdf").write_bytes(b"synthetic-pdf")
    (source / "register.csv").write_text("invoice,total\nA-1,100\n", encoding="utf-8")

    copied = MODULE.sync_frontend_demo_documents(source, target)

    assert copied == 2
    assert (target / "invoice.pdf").read_bytes() == b"synthetic-pdf"
    assert (target / "register.csv").read_text(encoding="utf-8") == "invoice,total\nA-1,100\n"
