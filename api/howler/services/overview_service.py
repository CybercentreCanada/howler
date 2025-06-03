from pathlib import Path


def get_example_overviews() -> dict[str, str]:
    "Get a list of example overviews in the form of markdown files"
    overviews: dict[str, str] = {}

    for _file in (Path(__file__).parent.parent / "overviews").iterdir():
        if _file.suffix != ".md":
            continue

        overviews[_file.stem] = _file.read_text()

    return overviews
