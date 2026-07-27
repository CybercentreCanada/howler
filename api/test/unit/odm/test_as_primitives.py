import base64
import datetime
from ipaddress import ip_address

import pytest

from howler import odm


@pytest.fixture(scope="module")
def dummy_model() -> type[odm.Model]:
    @odm.model()
    class InnerModel(odm.Model):
        nested_ip_field = odm.IP()
        nested_timestamp_field = odm.Date()
        nested_keyword_field = odm.Keyword()

    @odm.model()
    class TestModel(odm.Model):
        ip_field = odm.IP()
        timestamp_field = odm.Date()
        keyword_field = odm.Keyword()
        ips_in_list = odm.List(odm.IP())
        ip_as_optional = odm.Optional(odm.IP())
        timestamp_in_mapping = odm.Mapping(odm.Date())
        inner_model_field = odm.Compound(InnerModel)

    return TestModel


@pytest.fixture(scope="module")
def timestamp_field():
    return datetime.datetime.fromisoformat("2026-01-01T00:00:00.000000+00:00")


@pytest.fixture(scope="module")
def timestamp_str():
    return "2026-01-01T00:00:00.000000Z"


@pytest.fixture(scope="module")
def timestamp_posix():
    return int(datetime.datetime.fromisoformat("2026-01-01T00:00:00.000000+00:00").timestamp())


@pytest.fixture(scope="module")
def model_data(timestamp_str) -> dict:
    return {
        "ip_field": "127.0.0.1",
        "timestamp_field": timestamp_str,
        "keyword_field": "test_keyword_containing_an_127.0.0.1_ip_address",
        "ips_in_list": ["1.1.1.1", "ff02::1"],
        "ip_as_optional": "192.168.0.1",
        "timestamp_in_mapping": {"key": timestamp_str},
        "inner_model_field": {
            "nested_ip_field": "10.0.0.1",
            "nested_timestamp_field": timestamp_str,
            "nested_keyword_field": f"nested_test_keyword_containing_a_{timestamp_str}_timestamp",
        },
    }


@pytest.fixture(scope="module")
def model_instance(dummy_model, model_data):
    return dummy_model(data=model_data)


def _check_json_serializable(data):
    """Check if the data is JSON serializable."""
    import json

    try:
        json.dumps(data)
        return True, ""
    except (TypeError, OverflowError) as e:
        return False, f"Data is not JSON serializable: {e}"


def test_as_primitives_default_uses_field_validator(model_instance, model_data):
    primitives = model_instance.as_primitives()
    for key, value in model_data.items():
        assert primitives[key] == value, f"Expected {key} to be {value}, but got {primitives[key]}"


@pytest.mark.parametrize(
    "format_arg, expected_type",
    [
        ("encoded_bytes", str),
        ("int", int),
        ("str", str),
    ],
)
def test_as_primitives_ip_format(format_arg, expected_type, model_instance, model_data):
    primitives = model_instance.as_primitives(ip_format=format_arg)

    check, hint = _check_json_serializable(primitives)
    assert check, hint

    ip_value = primitives.pop("ip_field")
    ip_list = primitives.pop("ips_in_list")
    ip_optional = primitives.pop("ip_as_optional")
    nested_field = primitives.pop("inner_model_field")
    nested_ip_field = nested_field.pop("nested_ip_field")

    assert isinstance(ip_value, expected_type), (
        f"Expected ip_field to be of type {expected_type}, but got {type(ip_value)}"
    )

    for ip in ip_list:
        assert isinstance(ip, expected_type), (
            f"Expected ips in list to contain elements of type {expected_type}, but got {type(ip)}"
        )

    assert isinstance(ip_optional, expected_type), (
        f"Expected ip declared as optional to be of type {expected_type}, but got {type(ip_optional)}"
    )

    assert isinstance(nested_ip_field, expected_type), (
        f"Expected ip in nested field to be of type {expected_type}, but got {type(nested_ip_field)}"
    )

    # check that non-ip fields are unaffected
    for key, value in primitives.items():
        assert value == model_data[key], f"Expected {key} to be {model_data[key]}, but got {value}"
    for key, value in nested_field.items():
        assert value == model_data["inner_model_field"][key], (
            f"Expected inner_model_field.{key} to be {model_data['inner_model_field'][key]}, but got {value}"
        )


def test_as_primitives_ip_format_invalid_returns_default(model_instance, model_data):
    primitives = model_instance.as_primitives(ip_format="invalid_format")
    for key, value in primitives.items():
        assert value == model_data[key], f"Expected {key} to be {model_data[key]}, but got {value}"


def test_as_primitives_ip_format_none_returns_default(model_instance, model_data):
    primitives = model_instance.as_primitives(ip_format=None)
    for key, value in primitives.items():
        assert value == model_data[key], f"Expected {key} to be {model_data[key]}, but got {value}"


def test_as_primitives_ip_format_bytes_accurate_conversion(model_instance, model_data):
    primitives = model_instance.as_primitives(ip_format="encoded_bytes")

    assert base64.b64decode(primitives["ip_field"]) == ip_address(model_data["ip_field"]).packed
    assert all(
        base64.b64decode(ip) == ip_address(expected_ip).packed
        for ip, expected_ip in zip(primitives["ips_in_list"], model_data["ips_in_list"])
    )
    assert base64.b64decode(primitives["ip_as_optional"]) == ip_address(model_data["ip_as_optional"]).packed
    assert (
        base64.b64decode(primitives["inner_model_field"]["nested_ip_field"])
        == ip_address(model_data["inner_model_field"]["nested_ip_field"]).packed
    )


@pytest.mark.parametrize(
    "format_arg, expected_type",
    [
        ("iso", str),
        ("posix", int),
    ],
)
def test_as_primitives_timestamp_format(format_arg, expected_type, model_instance, model_data):
    primitives = model_instance.as_primitives(timestamp_format=format_arg)

    check, hint = _check_json_serializable(primitives)
    assert check, hint

    timestamp_value = primitives.pop("timestamp_field")
    timestamp_mapping = primitives.pop("timestamp_in_mapping")
    nested_field = primitives.pop("inner_model_field")
    nested_timestamp_field = nested_field.pop("nested_timestamp_field")

    assert isinstance(timestamp_value, expected_type), (
        f"Expected timestamp_field to be of type {expected_type}, but got {type(timestamp_value)}"
    )

    for key, value in timestamp_mapping.items():
        assert isinstance(value, expected_type), (
            f"Expected timestamp in mapping to contain elements of type {expected_type}, but got {type(value)}"
        )

    assert isinstance(nested_timestamp_field, expected_type), (
        f"Expected timestamp in nested field to be of type {expected_type}, but got {type(nested_timestamp_field)}"
    )

    # check that non-timestamp fields are unaffected
    for key, value in primitives.items():
        assert value == model_data[key], f"Expected {key} to be {model_data[key]}, but got {value}"
    for key, value in nested_field.items():
        assert value == model_data["inner_model_field"][key], (
            f"Expected inner_model_field.{key} to be {model_data['inner_model_field'][key]}, but got {value}"
        )


def test_as_primitives_timestamp_format_invalid_returns_default(model_instance, model_data):
    primitives = model_instance.as_primitives(timestamp_format="invalid_format")
    for key, value in primitives.items():
        assert value == model_data[key], f"Expected {key} to be {model_data[key]}, but got {value}"


def test_as_primitives_timestamp_format_none_returns_default(model_instance, model_data):
    primitives = model_instance.as_primitives(timestamp_format=None)
    for key, value in primitives.items():
        assert value == model_data[key], f"Expected {key} to be {model_data[key]}, but got {value}"


def test_as_primitives_timestamp_format_posix_accurate_conversion(model_instance, timestamp_posix):
    primitives = model_instance.as_primitives(timestamp_format="posix")

    assert primitives["timestamp_field"] == timestamp_posix
    assert primitives["timestamp_in_mapping"]["key"] == timestamp_posix
    assert primitives["inner_model_field"]["nested_timestamp_field"] == timestamp_posix
