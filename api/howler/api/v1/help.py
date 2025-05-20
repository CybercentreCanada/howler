from howler.api import make_subapi_blueprint, ok
from howler.common.swagger import generate_swagger_docs
from howler.config import CLASSIFICATION
from howler.security import api_login

SUB_API = "help"
classification_definition = CLASSIFICATION.get_parsed_classification_definition()

help_api = make_subapi_blueprint(SUB_API, api_version=1)
help_api._doc = "Provide information about the system configuration"


@generate_swagger_docs()
@help_api.route("/classification_definition")
@api_login(audit=False, check_xsrf_token=False)
def get_classification_definition(**_):
    """Return the current system classification definition

    Variables:
    None

    Arguments:
    None

    Result Example:
    A parsed classification definition. (This is more for internal use)
    """
    return ok(classification_definition)
