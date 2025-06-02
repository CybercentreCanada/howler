import re
import sys
from types import FrameType
from typing import cast
from urllib.parse import quote

INVALID_STREAM_SEARCH_PARAMS = ("deep_paging_id", "rows", "sort")
SEARCHABLE = ["hit"]
API = "v1"


class ClientError(Exception):
    "Generic Exception for the howler client"

    def __init__(self, message, status_code, api_response=None, api_version=None, resp_data=None):
        super(ClientError, self).__init__(message)
        self.api_response = api_response
        self.api_version = api_version
        self.status_code = status_code
        self.resp_data = resp_data


def _join_param(k, v):
    val = quote(str(v))
    if not val:
        return k
    return f"{k}={val}"


def _join_kw(kw):
    return "&".join([_join_param(k, v) for k, v in kw.items() if v is not None])


def api_path_by_module(obj, *args, **kw):
    """Calculate the API path using the class and method names as shown below:

    /api/v1/<class_name>/<method_name>/[arg1/[arg2/[...]]][?k1=v1[...]]
    """
    c = obj.__class__.__name__.lower()
    m = cast(FrameType, sys._getframe().f_back).f_code.co_name

    return api_path(f"{c}/{m}", *args, **kw)


def _param_ok(k):
    return k not in ("q", "df", "wt")


def api_path(prefix, *args, **kw):
    """Calculate the API path using the prefix as shown:

    /api/v1/<prefix>/[arg1/[arg2/[...]]][?k1=v1[...]]
    """
    path = "/".join(["api", API, prefix] + list(args))

    params_tuples = kw.pop("params_tuples", [])
    params = "&".join([_join_kw(kw)] + [_join_param(*e) for e in params_tuples if _param_ok(e)])
    if not params:
        return path

    return f"{path}?{params}"


def stream_output(output):
    "Stream the output of a response"

    def _do_stream(response):
        f = output
        if isinstance(output, str):
            f = open(output, "wb")
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
        if f != output:
            f.close()
        return True

    return _do_stream


def walk_api_path(obj, path, paths):
    "Walk a module and populate a provided list with the paths and their documentation"
    if isinstance(obj, int):
        return

    for m in dir(obj):
        mobj = getattr(obj, m)
        if m == "__call__":
            doc = str(mobj.__doc__)
            if doc in ("x.__call__(...) <==> x(...)", "Call self as a function."):
                doc = str(obj.__doc__)
            doc = doc.split("\n\n", 1)[0]
            doc = re.sub(r"\s+", " ", doc.strip())
            if doc != "For internal use.":
                paths.append(f'{".".join(path)}(): {doc}')

            continue
        elif m.startswith(("_", "im_")):
            continue

        walk_api_path(mobj, path + [m], paths)


def to_pascal_case(snake_str):
    "Convert a snake_case string to PascalCase"
    components = snake_str.split("_")
    return "".join(component.title() for component in components)


def to_camel_case(snake_str):
    "Convert a PascalCase string to snake_case"
    components = snake_str.split("_")
    return components[0] + "".join(component.title() for component in components[1:])
