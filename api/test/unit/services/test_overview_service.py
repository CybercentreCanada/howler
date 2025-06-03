from pathlib import Path

from howler.services import overview_service


def test_example_markdown():
    assert "basic_example" in overview_service.get_example_overviews()

    test_file = Path(overview_service.__file__).parent.parent / "overviews" / "test_not_markdown.txt"

    test_file.touch()

    assert "test_not_markdown" not in overview_service.get_example_overviews()

    test_file.unlink()
