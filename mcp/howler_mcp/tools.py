import re
from logging import getLogger
from typing import Any

import httpx
from fastmcp.server.dependencies import get_access_token, get_http_request
from mcp.server.auth.provider import AccessToken
from pydantic import BaseModel, Field

from howler_mcp.api import HowlerApiClient

# Safety limits to avoid oversized backend requests.
MAXIMUM_TICKET: int = 200
MAXIMUM_OFFSET: int = 10000
# Reject ASCII control characters and path separators in path-bound
# identifiers such as hit_id.
CONTROL_OR_PATH_SEP_PATTERN = re.compile(r"[\x00-\x1F\x7F/\\]")

# Dossier update allowed keys
PERMITTED_KEYS = {
    "title",
    "query",
    "leads",
    "pivots",
    "type",
    "owner",
}
# API to get icons
ICONIFY_API = "https://api.iconify.design"
# supported languages
INTENDED_LANGUAGE: set = {"en", "fr"}

logger = getLogger(__name__)


class WhoAmIResponse(BaseModel):
    username: str = Field(description="Unique login name used to identify the current user in Howler.")
    email: str = Field(description="Primary email address associated with the user account.")
    groups: list[str] = Field(
        default_factory=list,
        description="Security or organizational groups the user belongs to.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Application roles granted to the user, such as admin or user.",
    )


# Structured response envelope returned by ``lucene_query``.
class HowlerResponse(BaseModel):
    rows: int = Field(description="Number of rows returned in the search results.")
    total: int = Field(description="Total number of hits matching the search criteria.")
    hits: list[dict[str, Any]] = Field(default_factory=list, description="List of hits matching the search criteria.")


def register_tools(mcp, api_client: HowlerApiClient):
    """Register all Howler MCP tools on the provided FastMCP instance.

    Args:
        mcp: FastMCP server instance used to register tool handlers.
        api_client: Shared API client used by tools to call the Howler backend.
    """
    # Cache searchable fields for this process to reduce mapping calls.
    cached_hit_fields: set[str] | None = None

    def _contains_escape_characters(value: str) -> bool:
        """Return True when value contains control chars or path separators."""
        return bool(CONTROL_OR_PATH_SEP_PATTERN.search(value))

    def _proper_access_token() -> AccessToken:
        """Return the current request access token or fail consistently."""
        request_available = False
        scope_user_available = False
        scope_token_type = "NoneType"
        auth_header_present = False
        request_path = "unknown"
        scope_access_token: Any = None

        try:
            request = get_http_request()
            # was not able to get request
            if not request:
                raise ValueError("request was receive empty")
            request_available = True

            scope_user = request.scope.get("user")
            # was not able to get user scope
            if not scope_user:
                raise ValueError("request did not contain the scope user")
            scope_user_available = True

            scope_access_token = getattr(scope_user, "access_token", None)
            scope_token_type = type(scope_access_token).__name__
            auth_header_present = bool(request.headers.get("authorization"))

            request_path = request.url.path
        except RuntimeError as e:
            logger.warning(f"auth_context_probe_failed error={e}")
        except ValueError as e:
            logger.warning(f"Server did not answer properly : {e}")

        access_token: AccessToken | None = None
        error: str = ""
        try:
            access_token = get_access_token()
        except (ValueError, TypeError) as e:
            # FastMCP may fail internal type checks even when request.scope.user
            # is present. Recover using the raw token value from the request
            # scope; only ``token`` is used downstream by HowlerApiClient.
            error = str(e)
            token_value = getattr(scope_access_token, "token", None)
            if token_value:
                access_token = AccessToken(
                    token=token_value,
                    client_id=getattr(scope_access_token, "client_id", "unknown-client"),
                    scopes=list(getattr(scope_access_token, "scopes", [])),
                    expires_at=getattr(scope_access_token, "expires_at", None),
                    resource=getattr(scope_access_token, "resource", None),
                )

        # get_access_token may return None without raising (expired background-task snapshot)
        if not access_token:
            raise ValueError(
                "Access token is not available. "
                f"request_available={request_available} "
                f"scope_user_available={scope_user_available} "
                f"scope_token_available={scope_access_token is not None} "
                f"scope_token_type={scope_token_type} "
                f"auth_header_present={auth_header_present} "
                f"request_path={request_path} "
                f"upstream_error={error}"
            )

        return access_token

    async def _validate_query_fields(query: str) -> str:
        """Normalize and validate field names referenced in a Lucene query.

        Args:
            query: Raw Lucene query provided by the caller.

        Returns:
            str: Normalized Lucene query with collapsed control whitespace.

        Raises:
            ValueError: If the query is empty after normalization or contains
                unsupported field names.
        """
        nonlocal cached_hit_fields

        # Normalize first so empty/whitespace-only queries are rejected early.
        normalized = re.sub(r"[\r\n\t]+", " ", query).strip()
        if not normalized:
            raise ValueError("query must be provided and cannot be empty.")

        # Match dotted field names only when they appear as field selectors
        # on the left side of a Lucene field:value expression.
        regex = r"\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*:"
        referenced_fields: list[str] = re.findall(regex, normalized)

        # Cache field metadata for the current process lifetime to avoid
        # re-fetching index mapping for every query validation.
        if cached_hit_fields is None:
            cached_hit_fields = set((await get_hit_fields()).keys())

        invalid_fields = sorted({field_name for field_name in referenced_fields if field_name not in cached_hit_fields})

        if invalid_fields:
            raise ValueError(
                f"Invalid query field(s): {', '.join(invalid_fields)}. Use get_hit_fields to list supported fields."
            )

        return normalized

    @mcp.tool(name="query_iconify")
    def query_iconify(query: str, limit: int = 30, prefix: str | None = None) -> set[str]:
        params: dict[str, str | int] = {"query": query, "limit": limit}
        if prefix is not None:
            params["prefix"] = prefix

        response = httpx.get(f"{ICONIFY_API}/search", params=params, timeout=10)
        response.raise_for_status()

        return set(response.json().get("icons", []))

    @mcp.tool(name="get_iconify_exist")
    def get_iconify_exist(icon_id: str) -> bool:
        prefix, _, name = icon_id.partition(":")
        url = f"{ICONIFY_API}/{prefix}/{name}.svg" if name else f"{ICONIFY_API}/{icon_id}"
        return httpx.get(url, timeout=10).status_code == 200

    @mcp.tool(name="whoami", description="Get information about the current user")
    async def whoami() -> WhoAmIResponse:
        """Return identity details for the authenticated Howler user.

        Use this tool when the user asks who they are authenticated as, what
        email address is tied to the session, or which groups and roles are
        currently available to them.

        Returns:
            WhoAmIResponse: Username, email, group membership, and role
            information for the current Howler user.
        """
        access_token: AccessToken = _proper_access_token()

        data = await api_client.call(
            user_access_token=access_token,
            path="/user/whoami",
            method="GET",
        )
        return WhoAmIResponse(
            username=data.get("username", ""),
            email=data.get("email", ""),
            groups=data.get("groups") or [],
            roles=data.get("roles") or [],
        )

    @mcp.tool(name="list_assigned_hits")
    async def list_assigned_hits() -> list[dict[str, Any]]:
        """Return hits assigned to the currently authenticated user.

        Use this tool when the user asks for their assigned hits or work queue.

        Returns:
            list[dict[str, Any]]: Hits returned by the Howler API for the
            current user's assignments.

        Raises:
            ValueError: If no access token is available.
        """
        access_token: AccessToken = _proper_access_token()

        return await api_client.call(
            user_access_token=access_token,
            path="/hit/user",
            method="GET",
        )

    @mcp.tool(name="add_comment_to_hit")
    async def add_comment_to_hit(hit_id: str, comment: str) -> str:
        """Add an analyst comment to a specific hit.

        Args:
            hit_id: Exact UUID of the hit that should receive the comment.
            comment: Comment text to append. The tool prefixes the text to show
                it originated from the MCP client.

        Returns:
            str: Confirmation message after the comment is added.

        Raises:
            ValueError: If no access token is available or if hit_id is invalid.
        """
        access_token: AccessToken = _proper_access_token()

        if not hit_id or not hit_id.strip():
            raise ValueError("hit_id is required and cannot be empty.")

        if _contains_escape_characters(hit_id):
            raise ValueError("hit_id cannot contain control characters or path separators.")

        hit_id = hit_id.strip()  # removing any space character

        await api_client.call(
            user_access_token=access_token,
            path=f"/hit/{hit_id}/comments",
            method="POST",
            body={"value": f"From MCP Client: {comment}"},
        )

        return "Comment added successfully."

    @mcp.tool(name="get_field_values")
    async def get_field_values(field: str) -> dict[str, int]:
        """Return the distinct values and their hit counts for a specific Howler hit field.

        Use this tool when you know a field name but are unsure which values it
        accepts. For example, call it with ``howler.escalation`` or
        ``howler.assessment`` before building a Lucene query that filters on
        those fields.

        Args:
            field: Exact field name to inspect, such as ``howler.escalation``
                or ``howler.assessment``.

        Returns:
            dict[str, int]: Mapping of distinct field value to the number of
            hits that carry it, for example
            ``{"alert": 120, "hit": 340, "miss": 5}``.

        Raises:
            ValueError: If no access token is available.
        """
        nonlocal cached_hit_fields

        access_token: AccessToken = _proper_access_token()

        normalized_field = field.strip()
        if not normalized_field:
            raise ValueError("field parameter is required")

        if cached_hit_fields is None:
            cached_hit_fields = set((await get_hit_fields()).keys())

        if normalized_field not in cached_hit_fields:
            raise ValueError(
                f"The field: {normalized_field} is not a valid option. Use get_hit_fields to see available fields."
            )

        field_values = await api_client.call(
            user_access_token=access_token,
            # The facet endpoint lives under /search/facet/<index>/<field>.
            # Passing the field directly in the path avoids a separate body.
            path=f"/search/facet/hit/{normalized_field}",
            method="GET",
            # A broad query is required — the facet endpoint needs at least one
            # matching document to return any distinct values. Using howler.id:*
            # matches every hit so we always get the full value distribution.
            params={"query": r"howler.id:*"},
        )

        return field_values

    @mcp.tool(name="get_hit_fields")
    async def get_hit_fields() -> dict[str, Any]:
        """Return all searchable fields available on Howler hits.

        Use this tool before building a Lucene query when you are unsure which
        field names are valid. The response lists every indexed field together
        with its type and whether it is stored or indexed.

        Returns:
            dict[str, Any]: Mapping of field name to field metadata, for
            example ``{"howler.assignment": {"type": "keyword", "indexed": true,
            "stored": false}, ...}``.

        Raises:
            ValueError: If no access token is available.
        """
        access_token: AccessToken = _proper_access_token()

        all_values: dict[str, Any] = await api_client.call(
            user_access_token=access_token,
            # /search/fields/<index> returns the Elasticsearch field mapping
            # for that index, including type, indexed, and stored flags.
            # This is the authoritative source of valid field names for
            # Lucene queries — use these names verbatim.
            path="/search/fields/hit",
            method="GET",
        )

        # Keep only the metadata required for query authoring.
        projected_values: dict[str, Any] = {}
        for key, values in all_values.items():
            # Somehow this key has no value?
            if not isinstance(values, dict):
                continue

            projected_values[key] = {
                "list": values.get("list"),
                "type": values.get("type"),
                "description": values.get("description"),
            }

        return projected_values

    @mcp.tool(name="lucene_query")
    async def lucene_query(
        query: str,
        fl: str,
        sort: str = "",
        rows: int = MAXIMUM_TICKET,
        offset: int = 0,
    ) -> HowlerResponse:
        """Search hits using a valid Lucene query.

        Use this tool when the user asks to search hits with explicit field/value
        criteria, boolean logic, ranges, or quoted phrases. The ``query`` argument
        must already be valid Lucene syntax.

        Common Howler fields:
            howler.id: Exact hit identifier.
            howler.assignment: Assigned user or queue.
            howler.escalation: Escalation state such as ``alert``.
            howler.assessment: Analyst assessment such as
                ``false-positive``.
            howler.analytic: Analytic name.
            howler.score: Numeric hit score.
            howler.outline.indicators: Indicator values extracted from the
                hit.
            howler.outline.target: Target values associated with the hit.
            howler.outline.threat: Threat values associated with the hit.
            event.created: Hit event timestamp, commonly used in time ranges.

        Examples:
            howler.assignment:user
            howler.analytic:"Password Checker"
            howler.escalation:alert AND event.created:[now-7d TO now]
            howler.score:[50 TO 100] AND NOT howler.assessment:false-positive
            howler.outline.indicators:(example.com OR 1.2.3.4)

        If you are unsure which field names are valid, call ``get_hit_fields``
        first. If you are unsure which values a field accepts, call
        ``get_field_values`` first.

        **Reducing response size with** ``fl``:

        Large responses (many hits or hits with long comment/log/dossier arrays)
        are written to a file that cannot be read back. Use ``fl`` to request
        only the fields you need so the response stays small enough to return
        inline.

        Pass ``fl`` as a comma-separated list of dot-notation field names.
        ``howler.id`` is always returned regardless of ``fl``.

        Examples:
            fl="howler.id,howler.assignment,howler.status"
            fl="howler.id,howler.analytic,howler.detection,howler.assessment"
            fl="howler.id,howler.outline.indicators,howler.outline.threat"

        Use ``fl`` to request the exact field(s) the user asked for so the
        response is as small as possible and does not require extra parsing.
        Example request: "Find me the detection for every ticket where the
        victim was 8.8.8.8" should request only detection (and ``howler.id``)
        in ``fl``, while filtering with the victim criterion in ``query``.

        Args:
            query: A valid Lucene query string. Use ``field:value`` syntax, quote
                phrase values that contain spaces, and use Lucene operators such as
                ``AND``, ``OR``, ``NOT``, parentheses, and range expressions.
                Do not invent field names or values. Use ``get_hit_fields`` and
                ``get_field_values`` to verify them before querying.
            sort: Optional Howler sort expression, such as
                ``event.created desc``. Leave empty to use the API default.
            rows: Maximum number of hits to return.
            offset: Starting offset into the result set for pagination.
            fl: Required comma-separated list of field names to include in each
                returned hit. Always pass only the exact fields requested by the
                user. ``howler.id`` is always added automatically if missing.

        Returns:
            HowlerResponse: Structured search results containing the total count,
            returned row count, and simplified hit payloads.
        """
        access_token: AccessToken = _proper_access_token()
        if not query or not query.strip():
            raise ValueError("query can not be empty or white spaces")

        query = await _validate_query_fields(query)

        if rows < 0 or rows > MAXIMUM_TICKET:
            raise ValueError(f"rows={rows} must be between 0 and {MAXIMUM_TICKET}.")

        if offset < 0 or offset > MAXIMUM_OFFSET:
            raise ValueError(f"offset={offset} must be between 0 and {MAXIMUM_OFFSET}.")

        if not fl.strip():
            raise ValueError("fl must be provided and cannot be empty.")

        # Build the POST body incrementally so that optional fields are only
        # sent when they carry a meaningful value.
        body: dict[str, Any] = {"query": query, "offset": offset, "rows": rows}
        if sort:
            # Only include sort when the caller explicitly set it. Sending an
            # empty string causes the API to reject the request rather than
            # falling back to its default sort order.
            body["sort"] = sort

        # Pass the field list to the API so it projects only the requested
        # fields server-side. The API expects a comma-separated string, not
        # a list — matching the "fl": "id,score" format in the data block.
        # howler.id is always included so hits remain identifiable.
        requested = list(dict.fromkeys(f.strip() for f in fl.split(",") if f.strip()))
        if "howler.id" not in requested:
            requested.insert(0, "howler.id")
        body["fl"] = ",".join(requested)

        data = await api_client.call(
            user_access_token=access_token,
            # The search endpoint accepts any Lucene query against the hit index.
            # The caller is responsible for providing valid Lucene syntax.
            path="/search/hit",
            method="POST",
            body=body,
        )

        return HowlerResponse(
            rows=data.get("rows", 0),
            total=data.get("total", 0),
            hits=data.get("items") or [],
        )

    @mcp.tool(name="get_label_set_options")
    async def get_label_set_options() -> list[str]:
        """Return the valid hit label categories supported by Howler.

        Returns:
            list[str]: Label category names derived from the searchable hit
                fields, for example ``generic`` or ``victim``.

        Raises:
            ValueError: If the request cannot be authenticated.
        """
        nonlocal cached_hit_fields

        # Load and cache the searchable field names once for this process.
        if cached_hit_fields is None:
            cached_hit_fields = set((await get_hit_fields()).keys())

        label_set_options: list[str] = []

        for field in cached_hit_fields:
            # Only keep hit label fields such as howler.labels.generic.
            if not field.startswith("howler.labels."):
                continue

            # Strip the common prefix so the caller gets just the label set
            # name, for example "generic" instead of "howler.labels.generic".
            label = field.replace("howler.labels.", "")

            if label == "":
                continue

            # Build the final list of supported label set options.
            label_set_options.append(label)

        return label_set_options

    @mcp.tool(name="add_label_to_hit")
    async def modify_label_to_hit(
        hit_id: str, labels_name: list[str], label_set: str, is_adding: bool = True
    ) -> list[str]:
        """Add one or more labels to a hit and return the updated label list.

        Args:
            hit_id: Howler hit identifier to update.
            labels_name: Label values to add to the hit.
            label_set: Label category to update, for example ``generic`` or
                ``victim``.

        Returns:
            list[str]: Updated list of labels for the requested category.

        Raises:
            ValueError: If the hit id is empty, the label list is empty, or the
                request cannot be authenticated.
        """
        # The backend expects lower-case label categories in the URL path.
        label_set = label_set.lower()

        if not isinstance(labels_name, list) or len(labels_name) == 0:
            raise ValueError(f"Label_name require to be a not empty list of string {labels_name}")

        if not hit_id or not hit_id.strip():
            raise ValueError(f"hit_id require to be a none empty or white space string, received {hit_id}")

        # Return just the updated labels for the requested category to keep the
        # MCP tool response small and easy to consume.
        data: dict[str, Any] = await api_client.call(
            user_access_token=_proper_access_token(),
            path=f"/hit/{hit_id.strip()}/labels/{label_set}",
            method="PUT" if is_adding else "DELETE",
            body={"value": labels_name},
        )
        return data.get("howler", {}).get("labels", {}).get(label_set, [])

    def _verify_leads(leads: list[dict]) -> bool:
        """Validate locally-generated lead payloads before API submission.

        This helper performs lightweight structural validation on lead payloads
        produced by the MCP layer. It is intentionally narrower than backend
        validation: the goal is to catch obvious schema mistakes early and give
        the model clearer feedback before making a network request.

        Args:
            leads: List of lead dictionaries that should match the dossier lead
                schema.

        Returns:
            bool: ``False`` when validation completes without finding an
                error.

        Raises:
            ValueError: If a lead contains unexpected keys, references an
                invalid icon, contains empty required string values, or has an
                invalid localized label structure.
            TypeError: If metadata is not provided as a dictionary.
        """
        intended_key: set = {"icon", "label", "format", "content", "metadata"}

        for lead in leads:
            lead_keys = set(lead.keys())
            # Reject unexpected keys early so the caller sees the exact schema
            # mismatch before the request reaches the backend.
            if lead_keys - intended_key:
                raise ValueError(
                    f"A lead should have the keys {''.join(intended_key)} and the lead have {''.join(lead_keys)}"
                )

            # Mirror the UI's Iconify validation so the model only sends icon
            # IDs that the frontend can actually render.
            if not get_iconify_exist(lead["icon"]):
                raise ValueError(
                    f"The icon {lead['icon']} does not exist in iconify please use the function query_iconify to find a valid icon"
                )
            # Ensuring the values are the proper type, not necesserly accepted as the back end may change valid value, type are less likely
            for key in ("format", "content"):
                if not isinstance(lead[key], str) or not lead[key] or not lead[key].strip():
                    raise ValueError("label must be a none empty or white space string")
            if not isinstance(lead["metadata"], dict):
                raise TypeError(
                    "metadata key need to be a dictionary. It may be an empty dictionary. as it is an optional field"
                )

            # Require both supported localization keys so the generated dossier
            # can be rendered consistently in the bilingual UI.
            if lead["label"].keys() - INTENDED_LANGUAGE:
                raise ValueError(
                    f"the label key should contain the keys {''.join(INTENDED_LANGUAGE)} you gave {lead['label'].keys()}"
                )

        return False

    def _verify_pivots(pivots: list[dict]) -> bool:
        """Validate locally-generated pivot payloads before API submission.

        This helper checks the pivot structure used by dossier creation and
        update requests. It exists to catch obvious MCP-side payload mistakes,
        not to replace backend validation or business rules.

        Args:
            pivots: List of pivot dictionaries that should match the dossier
                pivot schema.

        Returns:
            bool: ``False`` when validation completes without finding an
                error.

        Raises:
            ValueError: If a pivot contains unexpected keys, references an
                invalid icon, contains empty required string values, or has an
                invalid localized label structure.
            TypeError: If mappings is not provided using the expected
                container type.
        """
        intended_key = {"icon", "label", "value", "format", "mappings"}
        mapping_keys = {"key", "field", "custom_value"}
        for pivot in pivots:
            if not isinstance(pivot, dict):
                raise TypeError("Each pivot must be a dictionary.")

            pivot_key = set(pivot)

            # Keep the accepted pivot shape explicit so malformed nested data
            # fails locally with a specific message.
            if pivot_key - intended_key:
                raise ValueError(
                    f"A pivot should have the keys {''.join(intended_key)}; your pivot has {''.join(pivot_key)}"
                )

            missing_keys = intended_key - pivot_key
            if missing_keys:
                raise ValueError(f"A pivot is missing required keys: {', '.join(sorted(missing_keys))}.")

            # Bit more verification then just having a type check but we can do it since we needed to query iconify to find what we can do anyway
            # it should just make the LLM better at making its request
            if not isinstance(pivot["icon"], str) or not pivot["icon"].strip():
                raise ValueError("The pivot icon must be a non-empty string.")
            if not get_iconify_exist(pivot["icon"]):
                raise ValueError(
                    f"Invalid image was given for {pivot['icon']} please use the query_iconify function to find one or get_iconify_exist to verify it exist"
                )

            # The frontend expects localized labels instead of a single title
            # string, so enforce the bilingual structure here.
            label = pivot["label"]
            if not isinstance(label, dict):
                raise TypeError("The pivot label must be a dictionary.")
            language = set(label)
            if language != INTENDED_LANGUAGE:
                raise ValueError(
                    f"Pivot's label key require to have only {''.join(INTENDED_LANGUAGE)} as keys you gave {''.join(language)}"
                )
            if any(not isinstance(value, str) or not value.strip() for value in label.values()):
                raise ValueError("Each pivot label value must be a non-empty string.")

            for key in ("value", "format"):
                value = pivot[key]
                if not isinstance(value, str):
                    raise TypeError(f"The key {key} require to be of type string")

                if not value.strip():
                    raise ValueError(f"the key {key} require to be a none empty and not whitespace string")

            # Pivots carry nested mapping definitions, so reject scalar or
            # otherwise malformed containers before hitting the API.
            mappings = pivot["mappings"]
            if not isinstance(mappings, list):
                raise TypeError("The key mappings must be a list of mapping dictionaries.")
            for mapping in mappings:
                if not isinstance(mapping, dict):
                    raise TypeError("Each pivot mapping must be a dictionary.")
                if set(mapping) - mapping_keys:
                    raise ValueError("A pivot mapping may contain only key, field, and custom_value.")
                if {"key", "field"} - set(mapping):
                    raise ValueError("Each pivot mapping requires key and field.")
                for key in ("key", "field"):
                    if not isinstance(mapping[key], str) or not mapping[key].strip():
                        raise ValueError(f"The mapping {key} must be a non-empty string.")
                if (
                    "custom_value" in mapping
                    and mapping["custom_value"] is not None
                    and not isinstance(mapping["custom_value"], str)
                ):
                    raise TypeError("The mapping custom_value must be a string or null.")

        return False

    @mcp.tool(name="create_dossier")
    async def create_dossier(dossier_data: dict) -> dict:
        """Create a new dossier from a validated Lucene query.

        Use this tool when the user wants to save a reusable query as a
        dossier for later investigation workflows.

        Args:
            new_dossier_name: Human-readable dossier title to create.
            query: Lucene query used to define dossier membership.
            dossier_type: Dossier visibility scope. Must be either
                ``global`` or ``personal``.

        Returns:
            dict: The created dossier data returned by the API.

        Raises:
            ValueError: If query is empty, if the dossier name is empty, or if
                dossier_type is not one of the supported values.

        {
            "title": "My dossier",
            "query": "howler.id:*",
            "type": "personal" or "global",
            "leads": [
                {
                    "icon": "mdi:file-document",
                    "label": {"en": "Overview", "fr": "Apercu"},
                    "format": "markdown",
                    "content": "Initial notes",
                    "metadata": {"source": "manual"},
                }
            ],
            "pivots": [
                {
                    "icon": "mdi:open-in-new",
                    "label": {"en": "Pivot Link", "fr": "Lien Pivot"},
                    "value": "https://example.local?q={ioc}",
                    "format": "link",
                    "mappings": [{"key": "ioc", "field": "howler.outline.indicators"}],
                }
            ],
        }
        """
        # verify these value has been fill first before doing the API call.
        # it is verified after in the call as well but this limit the LLM ability to send wrong data to the server and is faster to process
        needed_data_key: set[str] = {"title", "query", "type"}
        creation_keys = set(dossier_data.keys())

        if needed_data_key - creation_keys:
            raise ValueError(
                f"dossier_data require at minimum the fields {''.join(needed_data_key)} you have given {''.join(dossier_data.keys())}"
            )

        for key in needed_data_key:
            if not isinstance(dossier_data[key], str) or not dossier_data[key] or not dossier_data[key].strip():
                raise ValueError(f"dossier_data['{key}'] is required to be a none empty or not only white space string")

        # more involve check but this will help the LLM with values and limit the amount of fail query
        if dossier_data["type"] not in {"personal", "global"}:
            raise ValueError("The key type may only be fill by personal or global.")

        if "icon" in creation_keys and not get_iconify_exist(dossier_data["icon"]):
            raise ValueError(
                f"The icon {dossier_data['icon']} does not exist in iconify please use the function query_iconify to find a valid icon"
            )

        # Validate optional nested lead/pivot blocks locally so bad generated
        # payloads fail before the network call.
        if "leads" in creation_keys:
            _verify_leads(dossier_data.get("leads", []))

        if "pivots" in creation_keys:
            if not isinstance(dossier_data["pivots"], list):
                raise TypeError("The key pivots must be a list of dictionaries.")
            _verify_pivots(dossier_data["pivots"])

        dossier_data["query"] = await _validate_query_fields(dossier_data["query"])

        return await api_client.call(
            body=dossier_data,
            method="POST",
            path="/dossier/",
            user_access_token=_proper_access_token(),
        )

    @mcp.tool(name="update_dossier")
    async def update_dossier(dossier_id: str, data_to_update: dict[str, Any]) -> dict:
        """Update an existing dossier with a subset of permitted fields.

        Use this tool when the user wants to rename a dossier, change its
        query, or update other editable dossier attributes.

        Args:
            dossier_id: Identifier of the dossier to update.
            data_to_update: Partial dossier payload. Allowed keys are
                ``title``, ``query``, ``leads``, ``pivots``, ``type``, and
                ``owner``.

        Returns:
            bool: API response payload for the update operation.

        Raises:
            ValueError: If one or more keys in data_to_update are not
                permitted, or if query validation fails.
        """
        # Quick check that only data that can be updated are present
        data_update_keys: set = set(data_to_update.keys())
        for key in data_update_keys:
            if key not in PERMITTED_KEYS:
                raise ValueError(
                    f"The permitted keys for data_to_updates are : {', '.join(PERMITTED_KEYS)} you gave {''.join(data_update_keys)}"
                )

        # lets use our query checker to ensure we send proper data
        if "query" in data_update_keys:
            data_to_update["query"] = await _validate_query_fields(data_to_update["query"])
        # ensure the pivots are properly formated before sending
        # Reuse the same local nested validators for update payloads so MCP
        # requests stay consistent with create_dossier expectations.
        if "pivots" in data_update_keys:
            if not isinstance(data_to_update["pivots"], list):
                raise TypeError("The key pivots require to be a list of dictionary ")
            _verify_pivots(data_to_update["pivots"])

        # ensure the leads are properly formated before sending
        if "leads" in data_update_keys:
            if not isinstance(data_to_update["leads"], list):
                raise TypeError("The key leads require to be a list of dictionary")
            _verify_leads(data_to_update["leads"])

        return await api_client.call(
            body=data_to_update,
            method="PUT",
            path=f"/dossier/{dossier_id}",
            user_access_token=_proper_access_token(),
        )

    @mcp.tool(name="assign_hit")
    async def assign_hit(hit_id: str, user_name: str) -> str:
        """Assign a hit to a user or release it from the current assignee.

        The tool uses two backend behaviors:
        - Assignment uses ``PUT /hit/<id>/update`` with a ``SET`` operation on
          ``howler.assignment``.
        - Release uses ``POST /hit/<id>/transition`` with
          ``{"transition": "release", "data": {}}`` when ``user_name`` is an
          empty string.

        Args:
            hit_id: Identifier of the hit to update.
            user_name: Username to assign to the hit. Provide an empty string
                to release/unassign the hit using the transition endpoint.

        Returns:
            str: The hit's ``howler.assignment`` value after the operation
            completes.

        Raises:
            ValueError: If ``hit_id`` is empty or contains disallowed path /
                control characters, or if ``user_name`` contains disallowed
                path / control characters.
        """
        if not hit_id or not hit_id.strip():
            raise ValueError("hit_id is required and cannot be empty.")

        if _contains_escape_characters(hit_id):
            raise ValueError("hit_id cannot contain control characters or path separators.")

        if _contains_escape_characters(user_name):
            raise ValueError("user_name cannot contain control characters or path separators.")

        if " " in hit_id:
            raise ValueError(f"hit_id cannot contain spaces : {hit_id}")

        if " " in user_name:
            raise ValueError(f"user_name cannot contain spaces : {user_name}")

        payload: dict | list

        # Set to use the proper path and action if we want to give or remove an assigment
        if user_name == "":
            payload = {"transition": "release", "data": {}}
            path = f"/hit/{hit_id}/transition"
            method = "POST"
        else:
            payload = [("SET", "howler.assignment", user_name)]
            path = f"/hit/{hit_id}/update"
            method = "PUT"

        data = await api_client.call(
            body=payload,
            method=method,
            user_access_token=_proper_access_token(),
            path=path,
        )

        assignment = data.get("howler", {}).get("assignment", "unknown")
        return (
            f"Actual assignment is now : {assignment}"
            if assignment != "unknown"
            else "The server did not return apropriate data, can not verify if the change was made"
        )
