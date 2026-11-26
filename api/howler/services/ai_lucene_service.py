"""Stream natural-language to Lucene query generation from the configured AI provider."""

import json
import re
from collections.abc import Iterable, Iterator
from functools import lru_cache
from threading import BoundedSemaphore
from typing import Any, cast

from elasticsearch._sync.client.indices import IndicesClient
from werkzeug.wsgi import ClosingIterator

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.config import config
from howler.odm.base import Enum
from howler.services import agent_service, ai_service
from howler.services.ai_service import AIUpdate

logger = get_logger(__file__)

_slots: BoundedSemaphore | None = None


class GenerationBusyError(Exception):
    """Raised when this process is already running the maximum number of query generations."""


CODE_FENCE = re.compile(r"```[\w-]*[ \t]*\n?(?P<body>.*?)\n?```", re.DOTALL)
OPENING_FENCE = re.compile(r"```[\w-]*[ \t]*\n")


def is_available() -> bool:
    """Return whether Lucene query generation is enabled and its provider is configured."""
    lucene = config.core.ai.lucene
    if not lucene.enabled:
        return False

    if lucene.provider == "agent":
        return agent_service.has_delegation()

    return config.core.ai.enabled


def has_credential(token: str | None) -> bool:
    """Return whether the request can authenticate to the configured provider.

    The agent provider always requires the user's bearer token for delegation; the OpenAI provider can use
    a configured API key instead.
    """
    if config.core.ai.lucene.provider == "agent":
        return bool(token)

    return bool(config.core.ai.api_key or token)


def validate_request(prompt: Any, query: Any) -> str | None:
    """Validate a generation request.

    Args:
        prompt: Natural-language analyst request.
        query: Optional current Lucene query to refine.

    Returns:
        A user-visible error, or ``None`` when the request is valid.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return "A natural-language prompt is required."

    if len(prompt) > config.core.ai.lucene.max_prompt_chars:
        return f"The prompt cannot exceed {config.core.ai.lucene.max_prompt_chars} characters."

    if query is not None and not isinstance(query, str):
        return "The current query must be a string."

    return None


@lru_cache(maxsize=1)
def _field_context() -> str:
    """Describe searchable hit fields, including allowed enumerated values."""
    model_class = datastore().hit.model_class
    fields = model_class.flat_fields(skip_mappings=True) if model_class else {}

    lines = []
    for name, field in sorted(fields.items()):
        if isinstance(field, Enum):
            lines.append(f"{name}: enum[{'|'.join(sorted(field.values))}]")
        else:
            lines.append(f"{name}: {type(field).__name__.lower()}")

    return "\n".join(lines)


def _request_text(prompt: str, query: str | None) -> str:
    text = f"Request:\n{prompt.strip()}"
    if query and query.strip() and query.strip() != "*:*":
        text += f"\n\nCurrent query:\n{query.strip()}"
    return text


def build_messages(prompt: str, query: str | None) -> list[dict[str, str]]:
    """Build OpenAI-compatible chat messages, including the searchable field list.

    Args:
        prompt: Natural-language analyst request.
        query: Optional current Lucene query to refine.

    Returns:
        OpenAI-compatible chat messages.
    """
    system_prompt = f"{config.core.ai.lucene.system_prompt}\n\nSearchable hit fields (name: type):\n{_field_context()}"

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _request_text(prompt, query)},
    ]


def build_agent_text(prompt: str, query: str | None) -> str:
    """Build a single A2A message for the AI agent.

    The field list is omitted because the agent can look fields up with the Howler MCP tools.
    """
    return f"{config.core.ai.lucene.system_prompt}\n\n{_request_text(prompt, query)}"


def clean_query(text: str) -> str:
    """Extract the query from markdown wrappers that models sometimes add."""
    text = text.strip()
    match = CODE_FENCE.search(text)
    if match:
        text = match.group("body").strip()

    if len(text) > 1 and text.startswith("`") and text.endswith("`"):
        text = text.strip("`").strip()

    return text


def partial_query(text: str) -> str:
    """Extract the query from a response that is still being generated.

    Only the fenced code block is placed in the search bar, so nothing is returned until it opens, and the
    explanation that follows it is excluded.
    """
    match = OPENING_FENCE.search(text)
    if not match:
        return ""

    body = text[match.end() :]
    end = body.find("```")
    return (body[:end] if end != -1 else body).rstrip("`").strip()


def _event(data: dict[str, str], event: str | None = None) -> str:
    """Format a server-sent event."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _openai_updates(messages: list[dict[str, str]], token: str | None) -> Iterator[AIUpdate]:
    text = ""
    for delta in ai_service.stream_chat(config.core.ai, token, messages, model=config.core.ai.lucene.model):
        text += delta
        yield ("text", text)


def _query_warning(query: str) -> str | None:
    """Return a warning when Elasticsearch rejects the generated query, or ``None`` if it is valid."""
    try:
        collection = datastore().hit
        result = IndicesClient(collection.datastore.client).validate_query(q=query, index=collection.index_name)
    except Exception:
        logger.warning("Unable to validate a generated Lucene query", exc_info=True)
        return None

    if result.body.get("valid"):
        return None

    return "The generated query is not valid Lucene. Review it before searching."


def stream_events(updates: Iterator[AIUpdate]) -> Iterator[str]:
    """Convert provider updates into server-sent events.

    Emits ``data`` events with the query ``text`` generated so far and ``status`` events with agent
    progress, then a single ``done`` event with the cleaned query, the provider's full markdown
    ``response`` including its explanation, and an optional ``warning`` when the query is not valid
    Lucene. Failures end the stream with an ``error`` event with a safe reason.

    Args:
        updates: Provider text and status updates.

    Yields:
        Encoded server-sent events.
    """
    text = ""
    streamed = ""
    try:
        for kind, value in updates:
            if kind == "status":
                yield _event({"status": value}, "status")
                continue

            text = value
            if (query_so_far := partial_query(text)) and query_so_far != streamed:
                streamed = query_so_far
                yield _event({"text": streamed})
    except ai_service.AITransportError as exc:
        yield _event({"error": exc.reason}, "error")
        return
    except Exception:
        # Provider and transport errors can contain connection details or secrets.
        logger.error("Unexpected AI Lucene generation failure")  # noqa: TRY400
        yield _event({"error": "AI query generation failed."}, "error")
        return

    query = clean_query(text)
    if not query:
        yield _event({"error": "AI provider returned an empty query."}, "error")
        return

    done = {"query": query, "response": text.strip()}
    if warning := _query_warning(query):
        done["warning"] = warning

    yield _event(done, "done")


def _get_slots() -> BoundedSemaphore:
    global _slots
    if _slots is None:
        _slots = BoundedSemaphore(config.core.ai.lucene.max_concurrent)
    return _slots


def start_generation(prompt: str, query: str | None, token: str | None) -> Iterable[str]:
    """Reserve a generation slot, prepare provider access, and return the generation event stream.

    Agent delegation and broker exchanges run before streaming starts, so their failures can be
    reported as ordinary HTTP errors. The slot is released when the WSGI server closes the
    returned stream, including when the client disconnects.

    Raises:
        GenerationBusyError: If this process is already running ``max_concurrent`` generations.
        AITransportError: If agent access cannot be obtained.
    """
    slots = _get_slots()
    if not slots.acquire(blocking=False):
        raise GenerationBusyError()

    released = False

    def release() -> None:
        nonlocal released
        if not released:
            released = True
            slots.release()

    try:
        lucene = config.core.ai.lucene
        if lucene.provider == "agent":
            agent_token = agent_service.get_agent_token(lucene.agent, token or "")
            updates = agent_service.stream_message(lucene.agent, agent_token, build_agent_text(prompt, query))
        else:
            updates = _openai_updates(build_messages(prompt, query), token)
    except BaseException:
        release()
        raise

    # ClosingIterator is typed for bytes, but Flask responses encode str chunks.
    stream = ClosingIterator(stream_events(updates), release)  # type: ignore[arg-type]
    return cast(Iterable[str], stream)
