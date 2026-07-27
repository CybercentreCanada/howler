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
def model_data() -> dict:
    return {
        "ip_field": "127.0.0.1",
        "timestamp_field": "2026-01-01T00:00:00.000000Z",
        "keyword_field": "test_keyword",
        "ips_in_list": ["1.1.1.1", "ff02::1"],
        "ip_as_optional": "192.168.0.1",
        "timestamp_in_mapping": {"key": "2026-01-01T00:00:00.000000Z"},
        "inner_model_field": {
            "nested_ip_field": "10.0.0.1",
            "nested_timestamp_field": "2026-01-01T00:00:00.000000Z",
            "nested_keyword_field": "nested_test_keyword",
        },
    }


@pytest.fixture(scope="module")
def model_instance(dummy_model, model_data):
    return dummy_model(data=model_data)


def test_as_primitives_default_uses_field_validator(model_instance, model_data):
    primitives = model_instance.as_primitives()
    for key, value in model_data.items():
        assert primitives[key] == value, f"Expected {key} to be {value}, but got {primitives[key]}"
