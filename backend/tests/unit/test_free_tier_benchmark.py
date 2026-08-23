from pathlib import Path

from scripts.benchmark_free_tier_pipeline import discover_dataset_sets


def test_dataset_discovery_excludes_ground_truth_without_reading_it(tmp_path: Path) -> None:
    for set_number in range(1, 4):
        dataset = tmp_path / f"Set_{set_number:02d}_July_2026"
        dataset.mkdir()
        (dataset / "00_Set_Index_and_Ground_Truth.pdf").write_bytes(b"expected answers")
        for document_number in range(1, 8):
            (dataset / f"{document_number:02d}_Business.pdf").write_bytes(b"business data")

    discovered = discover_dataset_sets(tmp_path)

    assert len(discovered) == 3
    assert all(len(dataset.business_files) == 7 for dataset in discovered)
    assert all(len(dataset.excluded_references) == 1 for dataset in discovered)
    assert all(
        dataset.excluded_references[0].name == "00_Set_Index_and_Ground_Truth.pdf"
        for dataset in discovered
    )
