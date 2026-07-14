import pytest

from howler.common.swagger import generate_swagger_docs


@pytest.fixture(scope="module")
def docstring():
    return """Brief description of function.

        Arguments:
            arg1: float   => Description of arg1
            arg2        => Description of arg2

        Optional Arguments:
            arg3: boolean   => Description of arg3
        """


@pytest.fixture(scope="module")
def func_with_docstring(docstring):
    def test_func(**extra_args):
        pass

    test_func.__doc__ = docstring
    return test_func


@pytest.fixture(scope="module")
def func_with_path_params():
    def test_func(path_arg: int, **extra_args):
        pass

    return test_func


@pytest.fixture(scope="module")
def func_with_path_and_query_params():
    def test_func(path_arg: int, *, query_arg: str, query_arg_optional: int | None, **extra_args):
        pass

    return test_func


@pytest.fixture(scope="function")
def func_with_docstring_and_path_params(func_with_path_params, docstring):
    original_doc = func_with_path_params.__doc__
    func_with_path_params.__doc__ = docstring

    yield func_with_path_params

    func_with_path_params.__doc__ = original_doc


@pytest.fixture(scope="function")
def func_with_docstring_and_path_and_query_params(func_with_path_and_query_params, docstring):
    original_doc = func_with_path_and_query_params.__doc__
    func_with_path_and_query_params.__doc__ = docstring

    yield func_with_path_and_query_params

    func_with_path_and_query_params.__doc__ = original_doc


def test_spec_from_docstring(func_with_docstring):
    decorated = generate_swagger_docs()(func_with_docstring)

    assert hasattr(decorated, "specs_dict")
    assert decorated.specs_dict["parameters"] == [
        {"name": "arg1", "in": "query", "type": "number"},
        {"name": "arg2", "in": "query", "type": None},
        {"name": "arg3", "in": "query", "type": "boolean"},
    ]


def test_spec_from_path(func_with_path_params):
    decorated = generate_swagger_docs()(func_with_path_params)

    assert hasattr(decorated, "specs_dict")
    assert decorated.specs_dict["parameters"] == [
        {"name": "path_arg", "in": "path", "type": "string", "required": True}
    ]


def test_spec_from_path_and_query(func_with_path_and_query_params):
    decorated = generate_swagger_docs()(func_with_path_and_query_params)

    assert hasattr(decorated, "specs_dict")
    assert decorated.specs_dict["parameters"] == [
        {"name": "path_arg", "in": "path", "type": "string", "required": True},
        {"name": "query_arg", "in": "query", "type": "string", "required": True},
        {"name": "query_arg_optional", "in": "query", "type": "integer", "required": False},
    ]


def test_spec_from_docstring_and_path(func_with_docstring_and_path_params):
    decorated = generate_swagger_docs()(func_with_docstring_and_path_params)

    assert hasattr(decorated, "specs_dict")
    assert decorated.specs_dict["parameters"] == [
        {"name": "path_arg", "in": "path", "type": "string", "required": True},
        {"name": "arg1", "in": "query", "type": "number"},
        {"name": "arg2", "in": "query", "type": None},
        {"name": "arg3", "in": "query", "type": "boolean"},
    ]


def test_spec_from_docstring_and_path_and_query(func_with_docstring_and_path_and_query_params):
    decorated = generate_swagger_docs()(func_with_docstring_and_path_and_query_params)

    assert hasattr(decorated, "specs_dict")
    assert decorated.specs_dict["parameters"] == [
        {"name": "path_arg", "in": "path", "type": "string", "required": True},
        {"name": "query_arg", "in": "query", "type": "string", "required": True},
        {"name": "query_arg_optional", "in": "query", "type": "integer", "required": False},
        {"name": "arg1", "in": "query", "type": "number"},
        {"name": "arg2", "in": "query", "type": None},
        {"name": "arg3", "in": "query", "type": "boolean"},
    ]
