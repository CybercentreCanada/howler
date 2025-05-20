from flask import request

from howler.api import bad_request, internal_error, make_subapi_blueprint, ok
from howler.common.swagger import generate_swagger_docs
from howler.security import api_login
from howler.services import notebook_service

SUB_API = "notebook"
notebook_api = make_subapi_blueprint(SUB_API, api_version=1)
notebook_api._doc = "Get notebook information"


@generate_swagger_docs()
@notebook_api.route("/environments", methods=["GET"])
@api_login(required_priv=["R"], required_method=["oauth"])
def get_user_environments(**kwargs):
    """Get user's jupyter hub environments

    Variables:
    None

    Arguments:

    Result Example:
    {
        [
            Env1,
            Env2
        ]
    }
    """
    try:
        env = notebook_service.get_user_envs()

        return ok({"envs": env})
    except Exception as error:
        return internal_error(err=f"Failed to retrieve user's environments from nbgallery. {error}")


@generate_swagger_docs()
@notebook_api.route("/notebook", methods=["POST"])
@api_login(required_priv=["R"], required_method=["oauth"])
def get_notebook(**kwargs):
    """Return patched notebook

    Variables:
    None

    Arguments:


    Data Block:
    {
        link: "https://nbgallery...",
        analytic: Analytic object,
        hit: Hit object
    }

    Result Example:
    {
        [
            Env1,
            Env2
        ]
    }
    """
    data = request.json
    if not isinstance(data, dict):
        return bad_request(err="Invalid data format")

    if "link" not in data:
        return bad_request(err="You must provide a link")

    if "analytic" not in data:
        return bad_request(err="You must provide an analytic")

    try:
        json_content, name = notebook_service.get_nb_information(data["link"], data["analytic"], data.get("hit", {}))
    except Exception as error:
        return internal_error(err=f"Failed to retrieve notebook from nbgallery. {error}")

    return ok({"nb_content": json_content, "name": name})
