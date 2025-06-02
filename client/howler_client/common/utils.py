import hashlib
import re
import sys
import uuid

import baseconv

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote


INVALID_STREAM_SEARCH_PARAMS = ("deep_paging_id", "rows", "sort")
SEARCHABLE = ["hit"]
API = "v1"


class ClientError(Exception):
    def __init__(
        self, message, status_code, api_response=None, api_version=None, resp_data=None
    ):
        super(ClientError, self).__init__(message)
        self.api_response = api_response
        self.api_version = api_version
        self.status_code = status_code
        self.resp_data = resp_data


def _bool_to_param_string(b):
    if not isinstance(b, bool):
        return b
    return {True: "true", False: "false"}[b]


def _join_param(k, v):
    val = quote(str(v))
    if not val:
        return k
    return "=".join((k, val))


def _join_kw(kw):
    return "&".join([_join_param(k, v) for k, v in kw.items() if v is not None])


def _join_params(q, params):
    return "&".join([quote(q)] + [_join_param(*e) for e in params if _param_ok(e)])


def get_random_id():
    return baseconv.base62.encode(uuid.uuid4().int)


def get_id_from_path(path):
    sha256_hash = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    path_id = baseconv.base62.encode(int(sha256_hash, 16))
    return path_id


# noinspection PyProtectedMember
def get_function_kwargs(*ex):
    local_frames = sys._getframe().f_back.f_locals  # pylint: disable=W0212
    return {k: _bool_to_param_string(v) for k, v in local_frames.items() if k not in ex}


# Calculate the API path using the class and method names as shown below:
#
#     /api/v1/<class_name>/<method_name>/[arg1/[arg2/[...]]][?k1=v1[...]]
#
# noinspection PyProtectedMember
def api_path_by_module(obj, *args, **kw):
    c = obj.__class__.__name__.lower()
    m = sys._getframe().f_back.f_code.co_name  # pylint:disable=W0212

    return api_path("/".join((c, m)), *args, **kw)


def _param_ok(k):
    return k not in ("q", "df", "wt")


# Calculate the API path using the prefix as shown:
#
#     /api/v1/<prefix>/[arg1/[arg2/[...]]][?k1=v1[...]]
#
def api_path(prefix, *args, **kw):
    path = "/".join(["api", API, prefix] + list(args))

    params_tuples = kw.pop("params_tuples", [])
    params = "&".join(
        [_join_kw(kw)] + [_join_param(*e) for e in params_tuples if _param_ok(e)]
    )
    if not params:
        return path

    return "?".join((path, params))


def raw_output(response):
    return response.content


def stream_output(output):
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
                paths.append([".".join(path), doc])
            continue
        elif m.startswith("_") or m.startswith("im_"):
            continue

        walk_api_path(mobj, path + [m], paths)


def to_pascal_case(snake_str):
    components = snake_str.split("_")
    return "".join(component.title() for component in components)


def to_camel_case(snake_str):
    components = snake_str.split("_")
    return components[0] + "".join(component.title() for component in components[1:])
