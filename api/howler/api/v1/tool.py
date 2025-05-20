from typing import Any, Optional

from flask import request

from howler.api import bad_request, created, make_subapi_blueprint
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.operations import OdmHelper
from howler.odm.base import _Field
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import action_service, analytic_service, hit_service
from howler.utils.dict_utils import flatten
from howler.utils.isotime import now_as_iso
from howler.utils.str_utils import get_parent_key
from howler.utils.uid import get_random_id

SUB_API = "tools"
tool_api = make_subapi_blueprint(SUB_API, api_version=1)
tool_api._doc = "Manage the tools"

FIELDS = Hit.flat_fields()

logger = get_logger(__file__)

hit_helper = OdmHelper(Hit)


@generate_swagger_docs()
@tool_api.route("/<tool_name>/hits", methods=["POST", "PUT"])
@api_login(required_priv=["W"])
def create_one_or_many_hits(tool_name: str, user: User, **kwargs):  # noqa: C901
    """Create one or many hits for a tool using field mapping.

    Variables:
    tool_name   => Name of the tool the hit is for

    Arguments:
    None

    Data Block:
    {
        "map": {            # For each field in the hit, list of field data will be copied to
            "source.field.in.raw.data": ["target.field.in.howler.hit.index"],
            ...
        },
        "hits": [           # List of raw hits to create the hit from
            {...},
            {...}
        ]
    }

    Result Example:
    {
        [                   # List of hits IDs/Errors created of the different hits (preserved order)
            {'id': "id1", 'error': None},
            {'id': "id2", 'error': None},
            {'id': None, 'error': "Error message"},
        ]
    }
    """
    data = request.json
    if not isinstance(data, dict):
        return bad_request(err="Invalid data format")

    field_map = data.pop("map", None)
    hits = data.pop("hits", None)
    ignore_extra_values: bool = bool(request.args.get("ignore_extra_values", False, type=lambda v: v.lower() == "true"))
    logger.debug(f"ignore_extra_values = {ignore_extra_values}")
    # Check data type
    if not isinstance(field_map, dict):
        return bad_request(err="Invalid: 'map' field is missing or invalid.")

    if not isinstance(hits, list):
        return bad_request(err="Invalid: 'hits' field is missing or invalid.")
    warnings = []
    # Validate field_map targets
    for targets in field_map.values():
        for target in targets:
            # This is checking to see if the target matches one of two cases:
            # Simple fields - hit.obj.key of type str (should match)
            # Compound fields - hit.obj of type dict (should also match)
            # This allows significantly easier creation of hits, since you don't need to deconstruct every dict into
            # individual fields
            if target not in FIELDS and not any(f for f in FIELDS.keys() if get_parent_key(f) == target):
                warning = f"Invalid target field in the map: {target}"
                if ignore_extra_values:
                    warnings.append(warning)
                    # field_map.pop(target)
                else:
                    return bad_request(err=warning)

    out: list[dict[str, Any]] = []
    odms = []
    bundle_hit: Optional[Hit] = None
    for hit in hits:
        cur_id = get_random_id()
        cur_time = now_as_iso()
        obj: dict[str, Any] = {
            "agent.type": tool_name,
            "event.created": cur_time,
            "event.id": cur_id,
            "howler.id": cur_id,
            "howler.analytic": tool_name,
            "howler.score": 0,
        }
        hit = flatten(hit)
        for source, targets in field_map.items():
            val = hit.get(source, None)
            if val is not None:
                for target in targets:
                    _val = val
                    try:
                        field_data: Optional[_Field] = FIELDS[target]
                    except KeyError:
                        logger.debug(f"`{target}` not in FIELDS")
                        field_data = next(
                            (v for k, v in FIELDS.items() if get_parent_key(k) == target),
                            None,
                        )

                    if field_data is not None and field_data.multivalued:
                        if not isinstance(_val, list):
                            _val = [val]
                        obj.setdefault(target, [])
                        obj[target].extend(_val)
                    else:
                        if isinstance(val, list):
                            if not len(val):
                                continue

                            _val = val[0]

                        obj[target] = _val

        try:
            odm, warns = hit_service.convert_hit(obj, unique=True, ignore_extra_values=ignore_extra_values)

            if odm.howler.is_bundle and bundle_hit is None:
                bundle_hit = odm
            elif odm.howler.is_bundle:
                return bad_request(err="You can only specify one bundle hit!")
            else:
                odms.append(odm)

            out.append(
                {
                    "id": odm.howler.id,
                    "error": None,
                    "warn": warns,
                }
            )
        except HowlerException as e:
            logger.warning(f"{type(e).__name__} when saving {cur_id}!")
            logger.warning(e)

            out.append({"id": None, "error": str(e)})
    # If there are any errors...
    if any([obj["error"] for obj in out]):
        return bad_request(out, warnings=warnings, err="No valid hits were provided")
    else:
        for odm in odms:
            if bundle_hit is not None:
                bundle_hit.howler.hits.append(odm.howler.id)
                bundle_hit.howler.bundle_size += 1
                odm.howler.bundles.append(bundle_hit.howler.id)

            hit_service.create_hit(odm.howler.id, odm, user=user["uname"])

            analytic_service.save_from_hit(odm, user)

        if bundle_hit:
            hit_service.create_hit(bundle_hit.howler.id, bundle_hit, user=user["uname"])

            analytic_service.save_from_hit(bundle_hit, user)

        datastore().hit.commit()

        action_service.bulk_execute_on_query(f"howler.id:({' OR '.join(entry['id'] for entry in out)})", user=user)

        return created(out, warnings=warnings)
