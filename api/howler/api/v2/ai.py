from flask import request

from howler.api import bad_gateway, bad_request, make_subapi_blueprint, stream_event_response, too_many_requests
from howler.common.swagger import generate_swagger_docs
from howler.security.login import api_login
from howler.services import ai_lucene_service, auth_service
from howler.services.ai_service import AITransportError

SUB_API = "ai"
ai_api = make_subapi_blueprint(SUB_API, api_version=2)
ai_api._doc = "Use the configured AI provider to assist analysts"  # type: ignore


@generate_swagger_docs()
@ai_api.route("/lucene", methods=["POST"])
@api_login(required_priv=["R"])
def generate_lucene(**kwargs):
    """Stream a Lucene hit query generated from a natural-language request.

    The response is a text/event-stream. Each default event contains the full text generated so
    far, "status" events report agent progress, and a single "done" event with the cleaned query
    or an "error" event ends the stream.

    Variables:
    None

    Arguments:
    None

    Data Block:
    {
        "prompt": "open hits escalated to alert in the last day",  # Natural-language request (required)
        "query": "howler.status:open"                           # Current query to refine (optional)
    }

    Result Example:
    event: status
    data: {"status": "Looking up hit fields"}

    data: {"text": "howler.status:open AND "}

    event: done
    data: {"query": "howler.status:open AND howler.escalation:alert"}

    The "done" event also contains a "warning" when the query is not valid Lucene.
    """
    if not ai_lucene_service.is_available():
        return bad_request(err="AI query generation is not enabled.")

    req_data = request.get_json(silent=True)
    if not isinstance(req_data, dict):
        return bad_request(err="Request body must be a JSON object.")

    prompt = req_data.get("prompt", "")
    query = req_data.get("query")
    if error := ai_lucene_service.validate_request(prompt, query):
        return bad_request(err=error)

    token = auth_service.get_token()
    if not ai_lucene_service.has_credential(token):
        return bad_request(err="AI query generation requires a Bearer authorization token.")

    try:
        events = ai_lucene_service.start_generation(prompt, query, token)
    except ai_lucene_service.GenerationBusyError:
        return too_many_requests(err="Too many AI query generations are running. Please retry shortly.")
    except AITransportError as exc:
        return bad_gateway(err=exc.reason)

    return stream_event_response(events)
