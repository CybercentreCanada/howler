import inspect
import re
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


def generate_swagger_docs(responses: dict[int, str] = {}):  # noqa: C901
    "Generate swagger documentation for a given endpoint"

    def decorator(function: Callable):  # noqa: ANN202
        "Decorator function for generating the swagger docs"
        func_signature = inspect.signature(function)
        func_doc = inspect.getdoc(function)
        if module := inspect.getmodule(function):
            module_name = module.__name__
        func_path = f"{module_name}.{function.__name__}" if module_name else function.__name__

        path_params = [
            {
                "name": param,
                "in": "path",
                "type": "string",
            }
            for param in func_signature.parameters
            if param not in ["kwargs", "_"] and not param.startswith("_")
        ]

        query_params: list[dict[str, Any]] = []
        if func_doc:
            for section in func_doc.split("\n\n"):
                lines = section.splitlines()
                if not lines[0].lower().endswith("arguments:"):
                    continue

                lines = [re.sub(r" =>.+", "", line).strip() for line in lines[1:]]

                for line in lines:
                    if line.lower() == "none" or "=>" not in line:
                        continue

                    if ": " in line:
                        name, type = line.split(": ")
                    else:
                        name = line
                        type = None

                    query_params.append({"name": name, "in": "query", "type": type})

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
