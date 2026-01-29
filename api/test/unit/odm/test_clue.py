import hashlib
import json

import pytest

from howler import odm
from howler.common.exceptions import HowlerValueError
from howler.odm.models.clue import Clue, TypeMap
from howler.odm.models.hit import Hit


def test_clue_model_creation():
    """Test basic Clue model creation with default values."""
    clue = Clue()
    assert clue.types == []
    assert isinstance(clue.types, list)


def test_clue_with_empty_list():
    """Test Clue creation with an empty types list."""
    clue = Clue({"types": []})
    assert clue.types == []


def test_clue_with_types_mapping():
    """Test Clue creation with a types mapping."""
    types_list = [
        {"field": "source.ip", "type": "ip"},
        {"field": "destination.ip", "type": "ip"},
        {"field": "user.name", "type": "username"},
        {"field": "file.hash.sha256", "type": "hash"},
    ]
    clue = Clue({"types": types_list})

    assert len(clue.types) == 4
    assert isinstance(clue.types[0], TypeMap)
    assert clue.types[0].field == "source.ip"
    assert clue.types[0].type == "ip"
    assert clue.types[1].field == "destination.ip"
    assert clue.types[1].type == "ip"
    assert clue.types[2].field == "user.name"
    assert clue.types[2].type == "username"
    assert clue.types[3].field == "file.hash.sha256"
    assert clue.types[3].type == "hash"


def test_clue_modification():
    """Test modifying Clue types after creation."""
    clue = Clue()
    assert clue.types == []

    # Add a new type mapping
    clue.types.append({"field": "source.ip", "type": "ip"})
    assert len(clue.types) == 1
    assert clue.types[0].field == "source.ip"
    assert clue.types[0].type == "ip"

    # Update existing type mapping
    clue.types[0].type = "ipv4"
    assert clue.types[0].type == "ipv4"

    # Add multiple mappings
    clue.types.append({"field": "destination.ip", "type": "ip"})
    clue.types.append({"field": "process.name", "type": "process_name"})

    assert len(clue.types) == 3
    assert clue.types[1].field == "destination.ip"
    assert clue.types[1].type == "ip"
    assert clue.types[2].field == "process.name"
    assert clue.types[2].type == "process_name"


def test_clue_as_primitives():
    """Test converting Clue to primitive types."""
    types_list = [
        {"field": "source.ip", "type": "ip"},
        {"field": "user.name", "type": "username"},
    ]
    clue = Clue({"types": types_list})
    primitives = clue.as_primitives()

    assert primitives == {"types": types_list}
    assert isinstance(primitives, dict)
    assert isinstance(primitives["types"], list)
    assert len(primitives["types"]) == 2


def test_clue_json_serialization():
    """Test JSON serialization and deserialization."""
    types_list = [
        {"field": "source.ip", "type": "ip"},
        {"field": "destination.port", "type": "port"},
        {"field": "file.name", "type": "filename"},
    ]
    clue = Clue({"types": types_list})

    # Serialize to JSON
    json_str = clue.json()
    assert isinstance(json_str, str)

    # Deserialize from JSON
    clue_restored = Clue(json.loads(json_str))
    assert len(clue_restored.types) == 3
    assert clue_restored.types[0].field == "source.ip"
    assert clue_restored.types[0].type == "ip"


def test_clue_fields():
    """Test Clue model fields structure."""
    fields = Clue.fields()

    assert "types" in fields
    assert isinstance(fields["types"], odm.List)


def test_clue_flat_fields():
    """Test Clue flat fields representation."""
    flat_fields = Clue.flat_fields()

    assert "types.field" in flat_fields


def test_add_clue_namespace_to_hit():
    """Test adding Clue as a namespace to the Hit model."""
    # Create a simple hit
    hit_data = {
        "howler": {
            "id": "test-hit-id",
            "analytic": "test-analytic",
            "hash": hashlib.sha256("example".encode()).hexdigest(),
        },
    }

    # Add clue namespace
    Hit.add_namespace(
        "clue",
        odm.Compound(Clue, description="Clue-specific overrides for this alert", default=None, optional=True),
    )

    try:
        # Create hit without clue
        hit = Hit(hit_data)
        assert hasattr(hit, "clue")
        assert hit.clue is None

        # Create hit with clue
        hit_with_clue_data = {
            **hit_data,
            "clue": {
                "types": [
                    {"field": "source.ip", "type": "ip"},
                    {"field": "destination.ip", "type": "ip"},
                ]
            },
        }
        hit_with_clue = Hit(hit_with_clue_data)
        assert hit_with_clue.clue is not None
        assert isinstance(hit_with_clue.clue, Clue)
        assert len(hit_with_clue.clue.types) == 2
        assert hit_with_clue.clue.types[0].field == "source.ip"
        assert hit_with_clue.clue.types[0].type == "ip"
    finally:
        # Clean up namespace
        Hit.remove_namespace("clue")


def test_hit_with_clue_modification():
    """Test modifying clue data on a hit."""
    # Add clue namespace
    Hit.add_namespace(
        "clue",
        odm.Compound(Clue, description="Clue-specific overrides for this alert", default=None, optional=True),
    )

    try:
        hit_data = {
            "howler": {
                "id": "test-hit-id",
                "analytic": "test-analytic",
                "hash": hashlib.sha256("example".encode()).hexdigest(),
            },
            "clue": {
                "types": [
                    {"field": "source.ip", "type": "ip"},
                ]
            },
        }

        hit = Hit(hit_data)
        assert hit.clue.types[0].field == "source.ip"
        assert hit.clue.types[0].type == "ip"

        # Modify clue types
        hit.clue.types.append({"field": "destination.port", "type": "port"})
        assert len(hit.clue.types) == 2
        assert hit.clue.types[1].field == "destination.port"
        assert hit.clue.types[1].type == "port"

        # Replace entire clue object
        new_clue = Clue(
            {
                "types": [
                    {"field": "file.name", "type": "filename"},
                    {"field": "process.name", "type": "process_name"},
                ]
            }
        )
        hit.clue = new_clue
        assert len(hit.clue.types) == 2
        assert hit.clue.types[0].field == "file.name"
        assert hit.clue.types[0].type == "filename"
        assert hit.clue.types[1].field == "process.name"
        assert hit.clue.types[1].type == "process_name"
    finally:
        # Clean up namespace
        Hit.remove_namespace("clue")


def test_hit_clue_flat_fields():
    """Test flat fields with clue namespace added to Hit."""
    # Add clue namespace
    Hit.add_namespace(
        "clue",
        odm.Compound(Clue, description="Clue-specific overrides for this alert", default=None, optional=True),
    )

    try:
        flat_fields = Hit.flat_fields()

        # Check that clue fields are present
        assert "clue" in flat_fields or any(key.startswith("clue.") for key in flat_fields)
        assert "clue.types.field" in flat_fields
    finally:
        # Clean up namespace
        Hit.remove_namespace("clue")


def test_clue_with_various_field_paths():
    """Test Clue with various complex field paths."""
    types_list = [
        # Simple field paths
        {"field": "source.ip", "type": "ip"},
        {"field": "destination.port", "type": "port"},
        # Nested field paths
        {"field": "file.hash.sha256", "type": "hash"},
        {"field": "file.hash.md5", "type": "hash"},
        {"field": "process.parent.name", "type": "process_name"},
        # ECS field paths
        {"field": "source.user.name", "type": "username"},
        {"field": "destination.user.email", "type": "email"},
        {"field": "threat.indicator.ip", "type": "ip"},
        # Howler-specific paths
        {"field": "howler.analytic", "type": "analytic_name"},
        {"field": "howler.detection", "type": "detection_method"},
    ]

    clue = Clue({"types": types_list})

    assert len(clue.types) == 10
    assert clue.types[0].field == "source.ip"
    assert clue.types[0].type == "ip"
    assert clue.types[2].field == "file.hash.sha256"
    assert clue.types[2].type == "hash"
    assert clue.types[4].field == "process.parent.name"
    assert clue.types[4].type == "process_name"


def test_clue_equality():
    """Test equality comparison for Clue objects."""
    types_list = [
        {"field": "source.ip", "type": "ip"},
        {"field": "destination.port", "type": "port"},
    ]

    clue1 = Clue({"types": types_list})
    clue2 = Clue({"types": types_list})
    clue3 = Clue({"types": [{"field": "source.ip", "type": "ipv4"}]})

    assert clue1 == clue2
    assert clue1 != clue3


def test_clue_empty_values():
    """Test Clue with empty strings in type values."""
    with pytest.raises(HowlerValueError):
        Clue(
            {
                "types": [
                    {"field": "source.ip", "type": "ip"},
                    {"field": "destination.ip", "type": ""},
                ]
            }
        )


def test_clue_with_special_characters():
    """Test Clue types with special characters in values."""
    types_list = [
        {"field": "source.ip", "type": "ip-address"},
        {"field": "user.name", "type": "user_name"},
        {"field": "file.path", "type": "file:path"},
        {"field": "custom.field", "type": "type-with-dashes"},
    ]

    clue = Clue({"types": types_list})

    assert clue.types[0].type == "ip-address"
    assert clue.types[1].type == "user_name"
    assert clue.types[2].type == "file:path"
    assert clue.types[3].type == "type-with-dashes"


def test_hit_clue_primitives():
    """Test converting a Hit with Clue to primitives."""
    # Add clue namespace
    Hit.add_namespace(
        "clue",
        odm.Compound(Clue, description="Clue-specific overrides for this alert", default=None, optional=True),
    )

    try:
        hit_data = {
            "howler": {
                "id": "test-hit-id",
                "analytic": "test-analytic",
                "hash": hashlib.sha256("example".encode()).hexdigest(),
            },
            "clue": {
                "types": [
                    {"field": "source.ip", "type": "ip"},
                    {"field": "destination.port", "type": "port"},
                ]
            },
        }

        hit = Hit(hit_data)
        primitives = hit.as_primitives()

        assert "clue" in primitives
        assert isinstance(primitives["clue"]["types"], list)
        assert primitives["clue"]["types"][0]["field"] == "source.ip"
        assert primitives["clue"]["types"][0]["type"] == "ip"
    finally:
        # Clean up namespace
        Hit.remove_namespace("clue")


def test_hit_clue_json_round_trip():
    """Test JSON serialization round trip for Hit with Clue."""
    # Add clue namespace
    Hit.add_namespace(
        "clue",
        odm.Compound(Clue, description="Clue-specific overrides for this alert", default=None, optional=True),
    )

    try:
        hit_data = {
            "howler": {
                "id": "test-hit-id",
                "analytic": "test-analytic",
                "hash": hashlib.sha256("example".encode()).hexdigest(),
            },
            "clue": {
                "types": [
                    {"field": "source.ip", "type": "ip"},
                    {"field": "file.hash.sha256", "type": "hash"},
                ]
            },
        }

        # Create hit
        hit1 = Hit(hit_data)

        # Serialize to JSON and back
        json_str = hit1.json()
        hit2 = Hit(json.loads(json_str))

        # Verify clue data is preserved
        assert hit2.clue is not None
        assert len(hit2.clue.types) == 2
        assert hit2.clue.types[0].field == "source.ip"
        assert hit2.clue.types[0].type == "ip"
        assert hit2.clue.types[1].field == "file.hash.sha256"
        assert hit2.clue.types[1].type == "hash"
    finally:
        # Clean up namespace
        Hit.remove_namespace("clue")


def test_clue_default_value():
    """Test that Clue has proper default value for types."""
    clue1 = Clue()
    clue2 = Clue({})

    # Both should have empty list as default
    assert clue1.types == []
    assert clue2.types == []

    # Modifying one should not affect the other
    clue1.types.append({"field": "test", "type": "value"})
    assert len(clue2.types) == 0


def test_hit_without_clue_when_optional():
    """Test that Hit can be created without clue when it's optional."""
    # Add clue namespace as optional
    Hit.add_namespace(
        "clue",
        odm.Optional(odm.Compound(Clue, description="Clue-specific overrides for this alert")),
    )

    try:
        hit_data = {
            "howler": {
                "id": "test-hit-id",
                "analytic": "test-analytic",
                "hash": hashlib.sha256("example".encode()).hexdigest(),
            },
        }

        hit = Hit(hit_data)

        # Clue should be None when not provided
        assert hit.clue is None
    finally:
        # Clean up namespace
        Hit.remove_namespace("clue")
