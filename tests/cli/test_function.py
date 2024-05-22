import pytest
import typer

from paka.cli.function import process_traffic_splits, validate_traffic_split


def test_validate_traffic_split() -> None:
    # Test valid input
    assert validate_traffic_split("rev1=20") == ("rev1", 20)

    # Test missing '='
    with pytest.raises(ValueError):
        validate_traffic_split("rev120")

    # Test non-numeric percentage
    with pytest.raises(ValueError):
        validate_traffic_split("rev1=twenty")

    # Test percentage out of range
    with pytest.raises(ValueError):
        validate_traffic_split("rev1=101")


def test_process_traffic_splits() -> None:
    # Test valid input
    splits, total = process_traffic_splits(["rev1=20", "rev2=30"])
    assert splits == [("rev1", 20), ("rev2", 30)]
    assert total == 50

    # Test duplicate revisions
    with pytest.raises(typer.Exit):
        process_traffic_splits(["rev1=20", "rev1=30"])

    # Test invalid split
    with pytest.raises(ValueError):
        process_traffic_splits(["rev1=20", "rev2=thirty"])
