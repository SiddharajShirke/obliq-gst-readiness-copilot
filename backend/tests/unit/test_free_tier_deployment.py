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
