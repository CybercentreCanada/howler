"""Stable helpers for Elasticsearch 9 response and exception representations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def response_body(response: Any) -> dict[str, Any]:
    """Return a decoded object response from a client wrapper or mapping."""
    body = getattr(response, "body", response)
    if not isinstance(body, Mapping):
        raise TypeError(f"Expected an Elasticsearch object response, got {type(body).__name__}")
    return dict(body)


def error_body(error: BaseException) -> dict[str, Any]:
    """Return the structured error body exposed by public client exceptions."""
    body = getattr(error, "body", None)
    if body is None:
        body = getattr(error, "info", None)
    return dict(body) if isinstance(body, Mapping) else {}


def error_status(error: BaseException) -> int | None:
    """Return an HTTP status without relying on legacy exception tuple layouts."""
    meta = getattr(error, "meta", None)
    status = getattr(meta, "status", None)
    if isinstance(status, int):
        return status
    if error.args:
        try:
            return int(error.args[0])
        except (TypeError, ValueError):
            return None
    return None


def error_type(error: BaseException) -> str | None:
    """Return Elasticsearch's structured error type identifier."""
    error_data = error_body(error).get("error")
    if not isinstance(error_data, Mapping):
        return str(error_data) if error_data else None
    root_causes = error_data.get("root_cause")
    if isinstance(root_causes, list) and root_causes and isinstance(root_causes[0], Mapping):
        root_type = root_causes[0].get("type")
        if root_type:
            return str(root_type)
    value = error_data.get("type")
    return str(value) if value else None


def error_message(error: BaseException) -> str:
    """Return the most useful public Elasticsearch error message available."""
    body = error_body(error)
    error_data = body.get("error")
    if isinstance(error_data, Mapping):
        root_causes = error_data.get("root_cause")
        if isinstance(root_causes, list) and root_causes and isinstance(root_causes[0], Mapping):
            reason = root_causes[0].get("reason")
            if reason:
                return str(reason)
        reason = error_data.get("reason")
        if reason:
            return str(reason)
        error_type = error_data.get("type")
        if error_type:
            return str(error_type)
    elif error_data:
        return str(error_data)
    return str(error)


def total_hits_value(total: Any) -> int:
    """Normalize Elasticsearch total-hit objects and legacy integer totals."""
    if isinstance(total, Mapping):
        total = total.get("value", 0)
    return int(total or 0)
