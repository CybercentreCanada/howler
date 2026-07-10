import inspect
import re
import types
from functools import wraps
from typing import Any, Callable, Optional, cast

from flasgger import utils


def monkey_patched_parse(obj, process_doc, endpoint=None, verb=None):
    """We monkey patch flasgger's built-in parse-docstring to work better with our format"""
    short_desc: Optional[str] = None
    long_desc: Optional[str] = None

    doc = inspect.getdoc(obj)

    if doc:
        short_desc = doc.splitlines()[0]
        long_desc = f"```\n{doc}\n```"

    return short_desc, long_desc, None


utils.parse_docstring = monkey_patched_parse


RESPONSES = {
    status_code: {
        "description": "Something went wrong with your request",
        "schema": {
            "type": "object",
            "properties": {
                "api_response": {"type": "string"},
                "api_error_message": {"type": "string"},
                "api_warning": {"type": "string"},
                "api_server_version": {"type": "string"},
                "api_status_code": {"type": "integer"},
            },
            "example": {
                "api_response": "Example response",
                "api_error_message": "Example error",
                "api_warning": "Example warning",
                "api_server_version": "1.0",
                "api_status_code": status_code,
            },
        },
    }
    for status_code in [400, 401, 403, 404]
}


PYTHON_TO_SWAGGER_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def generate_swagger_docs(responses: dict[int, str] = {}):  # noqa: C901
    "Generate swagger documentation for a given endpoint"

    def decorator(function: Callable):  # noqa: ANN202
        "Decorator function for generating the swagger docs"
        func_signature = inspect.signature(function)
        func_doc = inspect.getdoc(function)  # type: ignore
        module_name = None
        if module := inspect.getmodule(function):
            module_name = module.__name__
        func_path = f"{module_name}.{function.__name__}" if module_name else function.__name__

        path_params = [
            {
                "name": param_name,
                "in": "path",
                "type": "string",
                "required": True,
            }
            for param_name, param in func_signature.parameters.items()
            if param_name not in ["kwargs", "_"]
            and not param_name.startswith("_")
            and param.kind != inspect.Parameter.KEYWORD_ONLY
        ]

        query_params: list[dict[str, Any]] = _get_query_parameters(func_signature, func_doc)

        tags: list[str] = []
        if module := inspect.getmodule(function):
            tags.append(module.__name__.split(".")[-1].capitalize())

        cast(Any, function).specs_dict = {
            "parameters": [*path_params, *query_params],
            "responses": {
                "200": {
                    "description": responses.get(200, "Request succeeded"),
                    "schema": (None),
                },
                **RESPONSES,
            },
            "summary": "test",
            "tags": tags,
            "operationId": func_path,
        }

        @wraps(function)
        def wrapper(*args, **kwargs):
            return function(*args, **kwargs)

        return wrapper

    return decorator


def _get_query_parameters(func_signature: inspect.Signature, func_doc: Optional[str]) -> list[dict[str, Any]]:
    query_params = [
        {"name": param_name, "in": "query", **_get_annotated_classname(param)}
        for param_name, param in func_signature.parameters.items()
        if param.kind == inspect.Parameter.KEYWORD_ONLY  # query parameters requested using @parse_parameters
    ]

    # compatibility with old method of docstring-based query parameter definitions, prefer params in signature
    if func_doc:
        for section in func_doc.split("\n\n"):
            lines = section.splitlines()
            if not lines[0].lower().endswith("arguments:"):
                continue

            for line in lines:
                if line.lower() == "none" or "=>" not in line:
                    continue

                arg_def = re.sub(r" =>.+", "", line).strip()

                if ": " in arg_def:
                    name, type = arg_def.split(": ")
                else:
                    name = arg_def
                    type = None

                if not any(param["name"] == name for param in query_params):
                    query_params.append({"name": name, "in": "query", "type": type})

    return query_params


def _get_annotated_classname(param: inspect.Parameter) -> dict[str, list[dict[str, str]] | str | bool | None]:
    if param.annotation == inspect.Parameter.empty:
        return {"type": None}

    if isinstance(param.annotation, types.UnionType):
        required = types.NoneType not in param.annotation.__args__
        types_list = [PYTHON_TO_SWAGGER_TYPE_MAP.get(t, "object") for t in param.annotation.__args__]
        return {"oneOf": [{"type": t} for t in types_list], "required": required}

    return {"type": PYTHON_TO_SWAGGER_TYPE_MAP.get(param.annotation, "object"), "required": True}
