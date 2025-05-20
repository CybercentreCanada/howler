from textwrap import dedent

from flask import Blueprint, current_app, request

from howler.api import ok
from howler.security import api_login

API_PREFIX = "/api/v1"
apiv1 = Blueprint("apiv1", __name__, url_prefix=API_PREFIX)
apiv1._doc = "Api Documentation Version 1"  # type: ignore[attr-defined]


@apiv1.route("/")
@api_login(audit=False, required_priv=["R", "W"], required_type=["user", "admin"])
def get_api_documentation(**kwargs):
    """Full API doc.

    Loop through all registered API paths and display their documentation.
    Returns a list of API definition.

    Variables:
    None

    Arguments:
    None

    Result Example:
    [
        {
            'name': "Api Doc",                  # Name of the api
            'path': "/api/path/<variable>/",    # API path
            'ui_only': false,                   # Is UI only API
            'methods': ["GET", "POST"],         # Allowed HTTP methods
            'description': "API doc.",          # API documentation
            'id': "api_doc",                    # Unique ID for the API
            'function': "apiv1.api_doc",        # Function called in the code
            'protected': False,                 # Does the API require login?
            'required_type': ['user'],           # Type of users allowed to use API
            'complete' : True                   # Is the API stable?
        },
    ]
    """
    user_types = kwargs["user"]["type"]

    api_blueprints = {}
    api_list = []
    for rule in current_app.url_map.iter_rules():
        if rule.rule.startswith(request.path):
            methods = [item for item in (rule.methods or []) if item != "OPTIONS" and item != "HEAD"]

            func = current_app.view_functions[rule.endpoint]
            required_type = func.__dict__.get("required_type", ["user"])

            for u_type in user_types:
                if u_type in required_type:
                    doc_string = func.__doc__
                    func_title = " ".join(
                        [x.capitalize() for x in rule.endpoint[rule.endpoint.rindex(".") + 1 :].split("_")]
                    )
                    blueprint = rule.endpoint[: rule.endpoint.rindex(".")]
                    if blueprint == "apiv1":
                        blueprint = "documentation"

                    if blueprint not in api_blueprints:
                        try:
                            doc = current_app.blueprints[rule.endpoint[: rule.endpoint.rindex(".")]]._doc  # type: ignore[attr-defined]
                        except Exception:
                            doc = ""

                        api_blueprints[blueprint] = doc

                    if doc_string:
                        description = dedent(doc_string)
                    else:
                        description = "[INCOMPLETE]\n\nTHIS API HAS NOT BEEN DOCUMENTED YET!"

                    api_id = rule.endpoint.replace("apiv1.", "").replace(".", "_")

                    api_list.append(
                        {
                            "protected": func.__dict__.get("protected", False),
                            "required_type": sorted(required_type),
                            "name": func_title,
                            "id": api_id,
                            "function": f"api.v1.{rule.endpoint}",
                            "path": rule.rule,
                            "ui_only": rule.rule.startswith("%sui/" % request.path),
                            "methods": sorted(methods),
                            "description": description,
                            "complete": "[INCOMPLETE]" not in description,
                            "required_priv": func.__dict__.get("required_priv", []),
                        }
                    )

                    break

    return ok({"apis": api_list, "blueprints": api_blueprints})
