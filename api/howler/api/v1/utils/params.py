"""Parameter parsing and error handling reused across multiple endpoints."""

import functools
from typing import Any, Callable, Literal

from flask import request

from howler.api import bad_request
from howler.common.exceptions import HowlerInvalidParameterException

REFRESH_ARG_OPTIONS = ["true", "false", "wait_for"]

parser_t = Callable[[str | None], Any]


def parse_parameters(**requested_params: parser_t | Literal["required"] | tuple[parser_t, Literal["required"]] | None):
    """A decorator to parse required parameters from the request args.

    Usage:
        ```
        @app.route("/example")
        @parse_parameters(my_param=parse_func_def)
        def example_endpoint(*args, **kwargs):
            # can get result of parse_func_def(request.args.get("my_param"))
            my_param = kwargs.get("my_param")
            ...
        ```

    The parser function should take a single argument (the parameter value as a string)
    and return the parsed value. The parser function may raise a `HowlerInvalidParameterException`
    which will be returned as a 400_bad_request response with the message from the exception.

    If no parser function is needed, pass None as the value for the parameter,
    and the raw string value from the request args will be passed to the endpoint function.
    Alternatively, if the parameter is required but does not need parsing,
    pass "required" as the value for the parameter.

    Parser functions which normally accept None can also be marked as required
    by passing a tuple of (parser_func, "required") as the value for the parameter.
    """

    def decorator(func):

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                for param_name, parser in requested_params.items():
                    required_flag = None
                    if isinstance(parser, tuple):
                        parser, required_flag = parser

                    raw_value = request.args.get(param_name, None)

                    if parser == "required" or required_flag == "required":
                        if raw_value is None:
                            return bad_request(err=f"Missing required parameter: [{param_name}]")

                    kwargs[param_name] = parser(raw_value) if callable(parser) else raw_value

            except HowlerInvalidParameterException as e:
                return bad_request(err=e.message)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def int_parser(name: str, default: int, *, minimum: int, maximum: int | None = None) -> parser_t:
    """Build a parser that validates an integer query parameter within the given bounds."""

    def parse(raw_value: str | None) -> int:
        if raw_value is None:
            return default

        if not raw_value.isascii() or not raw_value.isdigit():
            raise HowlerInvalidParameterException(f"'{name}' must be an integer.")

        value = int(raw_value)
        if value < minimum:
            raise HowlerInvalidParameterException(f"'{name}' must be at least {minimum}.")
        if maximum is not None and value > maximum:
            raise HowlerInvalidParameterException(f"'{name}' must be at most {maximum}.")

        return value

    return parse


def parse_refresh(refresh: str | None):
    """Check the request args for the refresh flag and return the correct es key or a parse exception"""
    if refresh:
        refresh = refresh.lower()
        if refresh not in REFRESH_ARG_OPTIONS:
            raise HowlerInvalidParameterException(f"Invalid refresh option: [{refresh}]")
    return refresh
