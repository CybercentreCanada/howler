from copy import deepcopy
from threading import Lock
from typing import Any, Callable

from howler_client.common.utils import SEARCHABLE, ClientError, api_path


class _ScrollContext(object):
    """Request state for one active scroll token chain."""

    def __init__(self, index: str, query: str, search_kwargs: dict[str, Any]):
        self.index = index
        self.query = query
        self.search_kwargs = deepcopy(search_kwargs)
        self.scroll_id: str | None = None
        self.lock = Lock()


class Scroll(object):
    """Module for opening, advancing, and clearing v1 search scrolls.

    ``open`` returns the raw search response mapping. The returned
    ``next_deep_paging_id`` is retained with its index, query, and search options
    so ``next(scroll_id, keep_alive)`` can continue the exact request. Context is
    local to this ``Scroll`` instance, allowing independent scrolls on the same
    client without sharing their request state.
    """

    def __init__(self, connection: Any, do_search: Callable[..., dict[str, Any]]):
        self._connection = connection
        self._do_search = do_search
        self._contexts: dict[str, _ScrollContext] = {}
        self._contexts_lock = Lock()

    def open(self, index: str, query: str, keep_alive: str = "5m", **kwargs: Any) -> dict[str, Any]:
        """Open a scroll search and return its unmodified response mapping.

        Args:
            index: Searchable index to query (``hit`` or ``action``).
            query: Lucene query string.
            keep_alive: How long the scroll should remain available between requests.
            **kwargs: Search options such as ``rows``, ``filters``, and ``fl``. ``timeout`` applies only to the
                opening search and is not retained for subsequent pages.

        Returns:
            The exact search response mapping. If it contains
            ``next_deep_paging_id``, the request context is retained on this
            ``Scroll`` instance for ``next`` and ``clear``.
        """
        if index not in SEARCHABLE:
            raise ClientError("Index %s is not searchable" % index, 400)

        search_kwargs = deepcopy(kwargs)
        search_kwargs.pop("deep_paging_id", None)
        search_kwargs.pop("scroll", None)

        request_kwargs = deepcopy(search_kwargs)
        request_kwargs["scroll"] = keep_alive
        response = self._do_search(index, query, deep_paging_id="*", **request_kwargs)

        scroll_id = response.get("next_deep_paging_id")
        if isinstance(scroll_id, str) and scroll_id:
            context_kwargs = deepcopy(search_kwargs)
            context_kwargs.pop("timeout", None)
            context = _ScrollContext(index, query, context_kwargs)
            with self._contexts_lock:
                current_context = self._contexts.get(scroll_id)
                if current_context is not None and current_context is not context:
                    raise ClientError("The server returned a scroll ID already active in this client", 500)
                context.scroll_id = scroll_id
                self._contexts[scroll_id] = context

        return response

    def next(self, scroll_id: str, keep_alive: str) -> dict[str, Any]:
        """Continue a scroll using the latest ID returned by a previous page.

        Args:
            scroll_id: The latest ``next_deep_paging_id`` returned by this client's open/next call.
            keep_alive: How long the scroll should remain available after this request.

        Returns:
            The exact search response mapping. A terminal response may contain
            an empty ``items`` list; its context is then removed.

        Raises:
            ClientError: If ``scroll_id`` is unknown, expired, cleared, or no longer current.
        """
        with self._contexts_lock:
            context = self._contexts.get(scroll_id)

        if context is None:
            raise ClientError("Unknown or expired scroll ID: %s" % scroll_id, 400)

        with context.lock:
            with self._contexts_lock:
                if self._contexts.get(scroll_id) is not context:
                    raise ClientError("Unknown or expired scroll ID: %s" % scroll_id, 400)

            request_kwargs = deepcopy(context.search_kwargs)
            request_kwargs["scroll"] = keep_alive
            response = self._do_search(
                context.index,
                context.query,
                deep_paging_id=scroll_id,
                **request_kwargs,
            )

            next_scroll_id = response.get("next_deep_paging_id")
            if not isinstance(next_scroll_id, str) or not next_scroll_id:
                self._remove_context(context)
                return response

            with self._contexts_lock:
                conflicting_context = self._contexts.get(next_scroll_id)
                if conflicting_context is not None and conflicting_context is not context:
                    for token, registered_context in list(self._contexts.items()):
                        if registered_context is context:
                            del self._contexts[token]
                    context.scroll_id = None
                    raise ClientError("The server returned a scroll ID already active in this client", 500)

                if self._contexts.get(scroll_id) is context:
                    del self._contexts[scroll_id]
                context.scroll_id = next_scroll_id
                self._contexts[next_scroll_id] = context

            return response

    def clear(self, scroll_id: str) -> dict[str, Any] | None:
        """Clear a scroll and discard its retained request context.

        Args:
            scroll_id: The latest ``next_deep_paging_id`` returned by the search.

        Returns:
            The API response, if one is returned.
        """
        with self._contexts_lock:
            context = self._contexts.get(scroll_id)

        if context is None:
            response = self._connection.delete(api_path("search", "scroll"), json={"scroll_id": scroll_id})
            with self._contexts_lock:
                self._contexts.pop(scroll_id, None)
            return response

        with context.lock:
            with self._contexts_lock:
                current_scroll_id = context.scroll_id
                clear_id = (
                    current_scroll_id
                    if current_scroll_id and self._contexts.get(current_scroll_id) is context
                    else scroll_id
                )

            response = self._connection.delete(api_path("search", "scroll"), json={"scroll_id": clear_id})
            self._remove_context(context)
            return response

    def _remove_context(self, context: _ScrollContext) -> None:
        with self._contexts_lock:
            for token, registered_context in list(self._contexts.items()):
                if registered_context is context:
                    del self._contexts[token]
            context.scroll_id = None
