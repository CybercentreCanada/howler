from typing import Union

from howler.common.exceptions import HowlerNotImplementedError, HowlerValueError
from howler.common.logging import get_logger
from howler.datastore.constants import ANALYZER_MAPPING, NORMALIZER_MAPPING, TYPE_MAPPING
from howler.odm import (
    Any,
    Boolean,
    Classification,
    Compound,
    Date,
    FlattenedObject,
    Float,
    Integer,
    Json,
    Keyword,
    List,
    Mapping,
    Optional,
    Text,
)

logger = get_logger(__file__)


def build_mapping(field_data, prefix=None, allow_refuse_implicit=True):
    """The mapping for Elasticsearch based on a python model object."""
    prefix = prefix or []
    mappings = {}
    dynamic = []

    def set_mapping(temp_field, body):
        body["index"] = temp_field.index
        if body.get("type", "text") != "text":
            body["doc_values"] = temp_field.index
        if temp_field.copyto:
            if len(field.copyto) > 1:
                logger.warning("copyto field larger than 1, only using first entry")
            body["copy_to"] = temp_field.copyto[0]

        return body

    # Fill in the sections
    for field in field_data:
        path = prefix + ([field.name] if field.name else [])
        name = ".".join(path)

        if isinstance(field, Classification):
            mappings[name.strip(".")] = set_mapping(field, {"type": TYPE_MAPPING[field.__class__.__name__]})
            if "." not in name:
                mappings.update(
                    {
                        "__access_lvl__": {"type": "integer", "index": True},
                        "__access_req__": {"type": "keyword", "index": True},
                        "__access_grp1__": {"type": "keyword", "index": True},
                        "__access_grp2__": {"type": "keyword", "index": True},
                    }
                )

        elif isinstance(field, (Boolean, Integer, Float, Text)):
            mappings[name.strip(".")] = set_mapping(field, {"type": TYPE_MAPPING[field.__class__.__name__]})

        elif field.__class__ in ANALYZER_MAPPING:
            mappings[name.strip(".")] = set_mapping(
                field,
                {
                    "type": TYPE_MAPPING[field.__class__.__name__],
                    "analyzer": ANALYZER_MAPPING[field.__class__],
                },
            )

        elif isinstance(field, (Json, Keyword)):
            es_data_type = TYPE_MAPPING[field.__class__.__name__]
            data: dict[str, Union[str, int]] = {"type": es_data_type}
            if es_data_type == "keyword":
                data["ignore_above"] = 8191  # The maximum always safe value in elasticsearch
            if field.__class__ in NORMALIZER_MAPPING:
                data["normalizer"] = NORMALIZER_MAPPING[field.__class__]  # type: ignore
            mappings[name.strip(".")] = set_mapping(field, data)

        elif isinstance(field, Date):
            mappings[name.strip(".")] = set_mapping(
                field,
                {
                    "type": TYPE_MAPPING[field.__class__.__name__],
                    "format": "date_optional_time||epoch_millis",
                },
            )

        elif isinstance(field, FlattenedObject):
            if not field.index or isinstance(field.child_type, Any):
                mappings[name.strip(".")] = {"type": "object", "enabled": False}
            else:
                dynamic.extend(
                    build_templates(
                        f"{name}.*",
                        field.child_type,
                        nested_template=True,
                        index=field.index,
                    )
                )

        elif isinstance(field, List):
            temp_mappings, temp_dynamic = build_mapping([field.child_type], prefix=path, allow_refuse_implicit=False)
            mappings.update(temp_mappings)
            dynamic.extend(temp_dynamic)

        elif isinstance(field, Optional):
            temp_mappings, temp_dynamic = build_mapping([field.child_type], prefix=prefix, allow_refuse_implicit=False)
            mappings.update(temp_mappings)
            dynamic.extend(temp_dynamic)

        elif isinstance(field, Compound):
            temp_mappings, temp_dynamic = build_mapping(
                field.fields().values(), prefix=path, allow_refuse_implicit=False
            )
            mappings.update(temp_mappings)
            dynamic.extend(temp_dynamic)

        elif isinstance(field, Mapping):
            if not field.index or isinstance(field.child_type, Any):
                mappings[name.strip(".")] = {"type": "object", "enabled": False}
            else:
                dynamic.extend(build_templates(f"{name}.*", field.child_type, index=field.index))

        elif isinstance(field, Any):
            if field.index:
                raise HowlerValueError(f"Any may not be indexed: {name}")

            mappings[name.strip(".")] = {
                "type": "keyword",
                "index": False,
                "doc_values": False,
            }

        else:
            raise HowlerNotImplementedError(f"Unknown type for elasticsearch schema: {field.__class__}")

    # The final template must match everything and disable indexing
    # this effectively disables dynamic indexing EXCEPT for the templates
    # we have defined
    if not dynamic and allow_refuse_implicit:
        # We cannot use the dynamic type matching if others are in play because they conflict with each other
        # TODO: Find a way to make them work together.
        dynamic.append(
            {
                "refuse_all_implicit_mappings": {
                    "match": "*",
                    "mapping": {
                        "index": False,
                        "ignore_malformed": True,
                    },
                }
            }
        )

    return mappings, dynamic


def build_templates(name, field, nested_template=False, index=True) -> list:
    if isinstance(field, (Keyword, Boolean, Integer, Float, Text, Json)):
        if nested_template:
            main_template = {"match": f"{name}", "mapping": {"type": "nested"}}

            return [{f"nested_{name}": main_template}]
        else:
            field_template = {
                "path_match": name,
                "mapping": {
                    "type": TYPE_MAPPING[field.__class__.__name__],
                    "index": field.index,
                },
            }

            if field.copyto:
                if len(field.copyto) > 1:
                    logger.warning("copyto field larger than 1, only using first entry")
                field_template["mapping"]["copy_to"] = field.copyto[0]

            return [{f"{name}_tpl": field_template}]

    elif isinstance(field, Any) or not index:
        field_template = {
            "path_match": name,
            "mapping": {"type": "keyword", "index": False},
        }

        if field.index:
            raise HowlerValueError(f"Mapping to Any may not be indexed: {name}")
        return [{f"{name}_tpl": field_template}]

    elif isinstance(field, (Mapping, List)):
        temp_name = name
        if field.name:
            temp_name = f"{name}.{field.name}"
        return build_templates(temp_name, field.child_type, nested_template=True)

    elif isinstance(field, Compound):
        temp_name = name
        if field.name:
            temp_name = f"{name}.{field.name}"

        out = []
        for sub_name, sub_field in field.fields().items():
            sub_name = f"{temp_name}.{sub_name}"
            out.extend(build_templates(sub_name, sub_field))

        return out

    elif isinstance(field, Optional):
        return build_templates(name, field.child_type, nested_template=nested_template)

    else:
        raise HowlerNotImplementedError(f"Unknown type for elasticsearch dynamic mapping: {field.__class__}")
