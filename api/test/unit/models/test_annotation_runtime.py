"""Runtime compatibility checks for generated ``Annotated`` field types."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, get_args, get_origin

from pydantic.fields import FieldInfo

from howler.models.fields import HowlerFieldMetadata, _make_annotated, keyword, list_field


def test_make_annotated_preserves_generic_base_and_metadata_order() -> None:
    """Generic annotation arguments and metadata retain their exact order."""
    first_metadata = object()
    second_metadata = object()
    base_annotation = dict[str, list[int]]

    annotation = _make_annotated(base_annotation, first_metadata, second_metadata)

    assert get_origin(annotation) is Annotated
    assert get_args(annotation) == (base_annotation, first_metadata, second_metadata)


def test_list_field_preserves_nested_and_container_metadata() -> None:
    """List field metadata stays on the container while child metadata stays nested."""
    child = keyword(copyto="search", deprecated=True)
    annotation = list_field(child, alias="items", description="Searchable items")

    container_type, *container_metadata = get_args(annotation)
    child_type, *child_metadata = get_args(get_args(container_type)[0])
    container_howler_metadata = next(item for item in container_metadata if isinstance(item, HowlerFieldMetadata))
    child_howler_metadata = next(item for item in child_metadata if isinstance(item, HowlerFieldMetadata))
    container_field_info = next(item for item in container_metadata if isinstance(item, FieldInfo))

    assert get_origin(annotation) is Annotated
    assert get_origin(container_type) is list
    assert child_type is str
    assert container_howler_metadata.kind == "List"
    assert child_howler_metadata.kind == "Keyword"
    assert child_howler_metadata.copy_to == ("search",)
    assert container_metadata.index(container_howler_metadata) < container_metadata.index(container_field_info)
    assert container_field_info.alias == "items"
    assert container_field_info.description == "Searchable items"


def test_howler_models_imports_in_a_cold_interpreter() -> None:
    """The model package can be imported without an already-loaded parent process."""
    api_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(part for part in (str(api_root), env.get("PYTHONPATH", "")) if part)

    result = subprocess.run(
        [sys.executable, "-c", "import howler.models"],
        capture_output=True,
        check=False,
        cwd=api_root,
        env=env,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
