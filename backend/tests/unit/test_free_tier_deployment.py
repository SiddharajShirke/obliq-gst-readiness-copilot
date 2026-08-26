from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_backend_container_limits_workers_and_numeric_threads() -> None:
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "OMP_NUM_THREADS=1" in dockerfile
    assert "MKL_NUM_THREADS=1" in dockerfile
    assert "TOKENIZERS_PARALLELISM=false" in dockerfile
    assert "--workers 1" in dockerfile


def test_render_blueprint_uses_one_heavy_processing_slot() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "HEAVY_PROCESSING_CONCURRENCY" in blueprint
    assert 'value: "1"' in blueprint


def test_render_blueprint_pins_canonical_public_origins_and_supported_ai_model() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "https://obliq-gst-readiness-copilot.vercel.app" in blueprint
    assert blueprint.count("https://obliq-gst-readiness-copilot.onrender.com") >= 2
    assert '- key: ALLOW_LOCAL_WHATSAPP_LINKS\n        value: "false"' in blueprint
    assert "meta/llama-3.2-11b-vision-instruct" in blueprint
