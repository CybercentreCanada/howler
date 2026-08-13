import pytest
from flask import Flask, jsonify, make_response
from werkzeug.test import EnvironBuilder

from howler.api.v1.utils.params import parse_parameters
from howler.config import SECRET_KEY


@pytest.fixture(scope="module")
def sample_endpoint():
    def endpoint(**kwargs):
        return make_response(jsonify(kwargs), 200)

    return endpoint


@pytest.fixture(scope="module")
def test_client():
    app = Flask(__name__)
    app.config.update(SESSION_COOKIE_SECURE=False, SECRET_KEY=SECRET_KEY, PREFERRED_URL_SCHEME="http")
    app.config.update({"TESTING": True})

    with app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def test_case_valid(request):
    test_case = {
        "kwargs": request.param.get("kwargs"),
        "params": _environ_builder_from_queries(request.param.get("valid", [])),
    }

    return test_case


@pytest.fixture(scope="function")
def test_case_invalid(request):
    test_case = {
        "kwargs": request.param.get("kwargs"),
        "params": _environ_builder_from_queries(request.param.get("invalid", [])),
    }

    return test_case


def _environ_builder_from_queries(query_args_list):
    return [EnvironBuilder(method="GET", query_string=query_args) for query_args in query_args_list]


TEST_CASES = {
    "required_param_using_literal": {
        "kwargs": {"required_param": "required"},
        "valid": [
            {"required_param": ""},
            {"required_param": "some_value", "another_param": "value"},
            {"required_param": 12},
        ],
        "invalid": [{}, {"required_param": None}],
    },
    "required_param_using_tuple": {
        "kwargs": {"required_param": ("required", "required")},
        "valid": [{"required_param": ""}, {"required_param": "some_value"}, {"required_param": 12}],
        "invalid": [{}, {"required_param": None}],
    },
    "optional_param": {
        "kwargs": {"optional_param": None},
        "valid": [
            {"optional_param": ""},
            {"optional_param": "some_value"},
            {"optional_param": 12},
            {"optional_param": None},
        ],
        "invalid": [],
    },
    "string_parser": {
        "kwargs": {"string_param": lambda x: str(x) if x is not None else None},
        "valid": [{"string_param": ""}, {"string_param": "some_value"}, {"string_param": 12}, {"string_param": 4.5}],
        "invalid": [],
    },
    "custom_parser": {
        "kwargs": {
            "custom_param": lambda x: {"uppercase": x.upper(), "lowercase": x.lower()} if x is not None else None
        },
        "valid": [{"custom_param": "test"}, {"custom_param": "ANOTHER"}],
        "invalid": [],
    },
    "parser_with_required": {
        "kwargs": {"required_param": (lambda x: x.upper(), "required")},
        "valid": [{"required_param": ""}, {"required_param": "some_value"}],
        "invalid": [{}, {"required_param": None}],
    },
}


@pytest.mark.parametrize("test_case_valid", TEST_CASES.values(), ids=TEST_CASES.keys(), indirect=True)
def test_params_valid(sample_endpoint, test_case_valid, test_client):
    endpoint = parse_parameters(**test_case_valid["kwargs"])(sample_endpoint)

    for params in test_case_valid["params"]:
        with test_client.application.request_context(environ=params.get_environ()):
            result = endpoint()

            assert result.status_code == 200
            result_kwargs = result.get_json()
            for param in test_case_valid["kwargs"].keys():
                assert param in result_kwargs

                parser = test_case_valid["kwargs"][param]
                if isinstance(parser, tuple):
                    parser = parser[0]
                if callable(parser):
                    assert result_kwargs[param] == parser(params.args.get(param))


@pytest.mark.parametrize("test_case_invalid", TEST_CASES.values(), ids=TEST_CASES.keys(), indirect=True)
def test_params_invalid(sample_endpoint, test_case_invalid, test_client):
    endpoint = parse_parameters(**test_case_invalid["kwargs"])(sample_endpoint)

    for params in test_case_invalid["params"]:
        with test_client.application.request_context(environ=params.get_environ()):
            result = endpoint()

            assert result.status_code == 400
