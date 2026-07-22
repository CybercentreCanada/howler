from flask import Blueprint

from howler.api import ok
from howler.security import api_login
from howler.services import docs_service

API_PREFIX = "/api/v1"
apiv1 = Blueprint("apiv1", __name__, url_prefix=API_PREFIX)
apiv1._doc = "Api Documentation Version 1"  # type: ignore[attr-defined] # type: ignore


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

    return ok(docs_service.build_route_docs("v1", user_types))
