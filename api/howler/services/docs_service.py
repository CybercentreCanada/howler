from textwrap import dedent

from flask import current_app, request


def build_route_docs(user_types: list[str]):
    """This function iterates through all registered Flask routes.

    It generates documentation for those accessible by the specified user types. It collects
    route metadata including permissions, methods, descriptions, and completion status.

    Args:
        user_types (list[str]): List of user types to filter API routes by.
            Only routes that grant access to at least one of these user types
            will be included in the output.

    Returns:
        dict: A dictionary containing:
            - 'apis' (list[dict]): List of API endpoint documentation, each dict includes:
                - 'protected' (bool): Whether the endpoint requires authentication.
                - 'required_type' (list[str]): User types allowed to access this endpoint.
                - 'name' (str): Human-readable name of the endpoint.
                - 'id' (str): Unique identifier for the endpoint.
                - 'function' (str): Full Python function path.
                - 'path' (str): URL path of the endpoint.
                - 'ui_only' (bool): Whether endpoint is UI-only.
                - 'methods' (list[str]): HTTP methods supported (excluding OPTIONS and HEAD).
                - 'description' (str): Docstring documentation or incomplete marker.
                - 'complete' (bool): Whether the endpoint is fully documented.
                - 'required_priv' (list[str]): Required privileges for the endpoint.
            - 'blueprints' (dict[str, str]): Map of blueprint names to their documentation strings.

    Note:
        Endpoints without documentation are marked with "[INCOMPLETE]" prefix
        in their description and complete field set to False.
    """
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

    return {"apis": api_list, "blueprints": api_blueprints}
