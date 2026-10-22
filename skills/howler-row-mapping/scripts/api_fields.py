#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["howler-client==3.2.0"]
# ///
"""Materialize hit-index field metadata from the Howler API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from mapping import (
    MappingError,
    digest,
    reject_constant,
    unique_pairs,
    validate_fields_snapshot,
    write_json,
)


def check_api_url(api_url):
    """Require and normalize a trusted HTTPS origin for API requests."""
    try:
        parsed = urlsplit(api_url)
        _ = parsed.port
    except ValueError:
        raise MappingError("API URL is invalid") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.fragment
        or parsed.query
    ):
        raise MappingError(
            "API URL must be an HTTPS origin without credentials, path, query, or fragment"
        )
    return api_url.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    """Prevent forwarding bearer credentials to redirect targets."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Reject redirects rather than constructing a redirected request."""
        # Never forward the bearer credential to a redirect target.
        return None


def fetch_fields(api_url, token, opener=None):
    """Fetch and project hit-index fields from the authenticated REST endpoint."""
    api_url = check_api_url(api_url)
    if opener is None:
        opener = build_opener(NoRedirect())
    request = Request(  # noqa: S310 - API URL is restricted to HTTPS.
        f"{api_url}/api/v1/search/fields/hit",
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    try:
        with opener.open(request, timeout=120) as response:
            body = response.read()
    except HTTPError as error:
        status = error.code
        error.close()
        raise MappingError(f"Howler API field request failed (HTTP {status})") from None
    except (URLError, TimeoutError, OSError):
        raise MappingError("Howler API field request failed") from None

    try:
        envelope = json.loads(
            body, object_pairs_hook=unique_pairs, parse_constant=reject_constant
        )
    except (ValueError, UnicodeError):
        raise MappingError("Howler API returned invalid field metadata") from None
    if not isinstance(envelope, dict) or not isinstance(
        envelope.get("api_response"), dict
    ):
        raise MappingError("Howler API returned an unsupported field response")

    fields = {
        key: {
            "list": values.get("list"),
            "type": values.get("type"),
            "description": values.get("description"),
        }
        for key, values in envelope["api_response"].items()
        if isinstance(key, str) and isinstance(values, dict)
    }
    if not fields:
        raise MappingError("Howler API returned no hit-index field metadata")
    return fields


def run(args, token, fetch=fetch_fields):
    """Fetch field metadata and save a versioned, fingerprinted snapshot."""
    api_url = check_api_url(args.api_url)
    fields = fetch(api_url, token)
    snapshot = {
        "version": 2,
        "api_url": api_url,
        "fields_sha256": digest(fields),
        "fields": fields,
    }
    validate_fields_snapshot(snapshot)
    write_json(args.output, snapshot, args.replace)
    return {"field_count": len(fields)}


def main(argv=None):
    """Parse the fields command, execute it, and emit a redacted summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fields = commands.add_parser(
        "fields", help="materialize hit-index API metadata as a snapshot"
    )
    fields.add_argument(
        "--api-url", required=True, help="selected Howler HTTPS origin, without /api"
    )
    fields.add_argument(
        "--token-file", help="private API token file; alternatively HOWLER_JWT"
    )
    fields.add_argument("--output", required=True)
    fields.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    try:
        if (
            args.token_file
            and Path(args.token_file).resolve() == Path(args.output).resolve()
        ):
            raise MappingError("output must not overwrite the supplied credential file")  # noqa: TRY301
        token = (
            Path(args.token_file).read_text().strip()
            if args.token_file
            else os.environ.get("HOWLER_JWT", "").strip()
        )
        if not token:
            raise MappingError("provide a token with --token-file or HOWLER_JWT")  # noqa: TRY301
        summary = run(args, token)
        sys.stdout.write(
            json.dumps({"status": "success", "output_path": args.output, **summary})
            + "\n"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary must redact third-party errors.
        message = (
            str(exc)
            if isinstance(exc, MappingError)
            else f"API/file operation failed ({type(exc).__name__}); no data logged"
        )
        sys.stderr.write(json.dumps({"status": "failure", "error": message}) + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
