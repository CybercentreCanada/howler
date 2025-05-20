from flask import Blueprint, current_app, request

from howler.api import API_PREFIX, ok
from howler.security import api_login

api = Blueprint("api", __name__, url_prefix=API_PREFIX)


#####################################
# API list API (API inception)
@api.route("/")
@api_login(audit=False, required_priv=["R", "W"])
def api_version_list(**_):
    """List all available API versions.

    Variables:
    None

    Arguments:
    None

    Result Example:
    ["v1", "v2", "v3"]         #List of API versions available
    """
    api_list = []
    for rule in current_app.url_map.iter_rules():
        if rule.rule.startswith("/api/"):
            version = rule.rule[5:].split("/", 1)[0]
            if version not in api_list and version != "":
                try:
                    int(version[1:])
                except ValueError:
                    continue
                api_list.append(version)

    return ok(api_list)


@api.route("/site_map")
@api_login(required_type=["admin"], audit=False)
def site_map(**_):
    """Check if all pages have been protected by a login decorator

    Variables:
    None

    Arguments:
    unsafe_only                    => Only show unsafe pages

    Result Example:
    [                                #List of pages dictionary containing...
     {"function": views.default,     #Function name
      "url": "/",                    #Url to page
      "protected": true,             #Is function login protected
      "required_type": false,         #List of user type allowed to view the page
      "methods": ["GET"]},           #Methods allowed to access the page
    ]
    """
    pages = []
    for rule in current_app.url_map.iter_rules():
        func = current_app.view_functions[rule.endpoint]
        methods = [item for item in (rule.methods or []) if item != "OPTIONS" and item != "HEAD"]

        protected = func.__dict__.get("protected", False)
        required_type = func.__dict__.get("required_type", ["user"])
        audit = func.__dict__.get("audit", False)
        priv = func.__dict__.get("required_priv", "")
        if "/api/v1/" in rule.rule:
            prefix = "api.v1."
        else:
            prefix = ""

        if "unsafe_only" in request.args and protected:
            continue

        pages.append(
            {
                "function": f"{prefix}{rule.endpoint.replace('apiv1.', '')}",
                "url": rule.rule,
                "methods": methods,
                "protected": protected,
                "required_type": required_type,
                "audit": audit,
                "req_priv": priv,
            }
        )

    return ok(sorted(pages, key=lambda i: i["url"]))
