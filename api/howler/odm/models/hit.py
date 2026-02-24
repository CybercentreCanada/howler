# mypy: ignore-errors

from howler import odm
from howler.common.logging import get_logger
from howler.odm.models.howler_data import HowlerData
from howler.odm.models.record import Record

logger = get_logger(__file__)


@odm.model(
    index=True,
    store=True,
    description="Howler Outline schema which is an extended version of Elastic Common Schema (ECS)",
)
class Hit(Record):
    # Howler extended fields. Deviates from ECS
    howler: HowlerData = odm.Compound(
        HowlerData,
        description="Howler specific definition of the hit that matches the outline.",
        reference="https://confluence.devtools.cse-cst.gc.ca/display/~jjgalar/Hit+Schema",
    )


if __name__ == "__main__":
    from pprint import pprint

    fields = {k: f"{v.__class__.__name__}{' (array)' if v.multivalued else ''}" for k, v in Hit.flat_fields().items()}
    pprint(fields)  # noqa: T203
