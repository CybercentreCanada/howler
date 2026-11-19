from typing import Any, TypeVar, get_origin, overload

from mergedeep import Strategy, merge

from howler.common.exceptions import HowlerValueError
from howler.models import HowlerESModel
from howler.models.registry import model_annotation, model_registry, unwrap_annotation
from howler.models.user import User
from howler.security.utils import is_classification_accessible
from howler.utils.dict_utils import flatten

Record = TypeVar("Record", bound=HowlerESModel)


@overload
def prepare_overwrite(
    stored: dict[str, Any],
    updates: dict[str, Any],
    model: type[Record],
    *,
    user: User | None,
    replace: bool,
    flatten_patch_mappings: bool = False,
) -> Record: ...


@overload
def prepare_overwrite(
    stored: dict[str, Any],
    updates: dict[str, Any],
    model: None,
    *,
    user: User | None,
    replace: bool,
    flatten_patch_mappings: bool = False,
) -> dict[str, Any]: ...


def prepare_overwrite(
    stored: dict[str, Any],
    updates: dict[str, Any],
    model: type[Record] | None,
    *,
    user: User | None,
    replace: bool,
    flatten_patch_mappings: bool = False,
) -> Record | dict[str, Any]:
    """Merge a partial update, check the resulting classification, then validate the record.

    Only the stored copy has a synthetic index to discard. V1 accepts updates as leaf paths
    even within dynamic mappings; v2 preserves mapping fields when flattening both inputs.
    """
    source = {key: value for key, value in stored.items() if key != "__index"}
    patch_model = None if flatten_patch_mappings else model
    patch = flatten(updates, odm=patch_model, preserve_empty=False)
    fields = model_registry.flat_fields(model, show_compound=True) if model is not None else {}
    # Keep the original route-specific flattening for mappings and unknown fields. The
    # exceptions are string scalar empties (never stringify {}) and explicitly empty single
    # compounds, provided the latter do not shadow existing descendants.
    for key, value in list(patch.items()):
        field = fields.get(key)
        if value == {} and field is not None:
            annotation = unwrap_annotation(field.annotation)
            if annotation is str and (field.metadata is None or field.metadata.kind != "Json"):
                del patch[key]

    stored_leaves = flatten(source)
    for key, value in flatten(updates, odm=patch_model).items():
        field = fields.get(key)
        if (
            value == {}
            and field is not None
            and model_annotation(unwrap_annotation(field.annotation)) is not None
            and get_origin(unwrap_annotation(field.annotation)) is not list
            and not any(path.startswith(f"{key}.") for path in stored_leaves)
        ):
            patch[key] = value

    merged: dict[str, Any] = {}
    merge(
        merged,
        flatten(source, odm=model),
        patch,
        strategy=Strategy.REPLACE if replace else Strategy.ADDITIVE,
    )
    if not is_classification_accessible(user, merged.get("classification")):
        raise HowlerValueError(f"Cannot set classification to {merged.get('classification')}")
    return model.validate_howler(merged) if model is not None else merged
