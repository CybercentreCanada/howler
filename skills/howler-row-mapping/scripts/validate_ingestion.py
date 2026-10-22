#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["howler-client==3.2.0"]
# ///
"""Validate saved alert JSONL directly with Howler, without ingesting records."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from mapping import (
    MappingError,
    canonical,
    digest,
    ensure_no_howler_id,
    fields_from_file,
    reject_constant,
    rows_from_file,
    unique_pairs,
    write_json,
)


def origin(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise MappingError(
            "Howler URLs must be HTTPS without credentials, query, or fragment"
        )
    # Normalize the default HTTPS port, not arbitrary paths or hosts.
    return parsed.scheme, parsed.hostname, parsed.port or 443


def validation_url(api_url, mcp_url):
    if origin(api_url) != origin(mcp_url):
        raise MappingError(
            "API and saved MCP fields must belong to the same HTTPS origin"
        )
    if urlsplit(api_url).path not in ("", "/"):
        raise MappingError("--api-url must be the Howler origin, without /api or /mcp")
    return api_url.rstrip("/") + "/api/v2/ingest/hit/validate"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # In particular, never forward a bearer token to a redirect target.
        return None


def post_records(url, token, records):
    for record in records:
        ensure_no_howler_id(record)
    request = Request(
        url,
        data=canonical(records).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=120) as response:
            status, body = response.status, response.read()
    except HTTPError as exc:
        # Preserve error bodies privately; never echo them (they may contain records).
        status, body = exc.code, exc.read()
        exc.close()
    try:
        payload = json.loads(
            body, object_pairs_hook=unique_pairs, parse_constant=reject_constant
        )
    except (ValueError, UnicodeError):
        payload = {"unparsed_body": body.decode("utf-8", errors="replace")}
    return status, payload


def save_validation(args, token, snapshot, records, post=post_records):
    for record in records:
        ensure_no_howler_id(record)
    url = validation_url(args.api_url, snapshot["mcp_url"])
    status, envelope = post(url, token, records)
    data = envelope.get("api_response") if isinstance(envelope, dict) else None
    contract_ok = False
    errors = []
    if (
        status == 200
        and isinstance(envelope, dict)
        and not envelope.get("api_error_message")
        and isinstance(data, dict)
        and isinstance(data.get("valid"), list)
        and isinstance(data.get("invalid"), list)
    ):
        # Ensure every submitted object is represented exactly once, including duplicates.
        # Do not substitute backend-normalized records for the saved source/output files.
        try:
            returned = data["valid"] + [error["input"] for error in data["invalid"]]
            contract_ok = (
                all(isinstance(record, dict) for record in data["valid"])
                and all(
                    isinstance(error, dict) and isinstance(error.get("error"), str)
                    for error in data["invalid"]
                )
                and Counter(canonical(record) for record in returned)
                == Counter(canonical(record) for record in records)
            )
        except (KeyError, TypeError, ValueError):
            contract_ok = False
        if contract_ok:
            errors = data["invalid"]
    valid = bool(records) and contract_ok and not errors
    # Keep the existing result.valid/errors convention, plus the complete REST envelope.
    write_json(
        args.output,
        {
            "scope": "backend",
            "transport": "rest",
            "mcp_url": snapshot["mcp_url"],
            "api_url": args.api_url.rstrip("/"),
            "validation_url": url,
            "http_status": status,
            "response_contract_valid": contract_ok,
            "fields_sha256": snapshot["fields_sha256"],
            "records_sha256": digest(records),
            "record_count": len(records),
            "result": {"valid": valid, "errors": errors},
            "response": envelope,
        },
        args.replace,
    )
    return {
        "valid": valid,
        "error_count": len(errors),
        "http_status": status,
        "response_contract_valid": contract_ok,
    }


def run(args, token, post=post_records):
    snapshot = fields_from_file(args.fields)
    current = fields_from_file(args.current_fields)
    if (
        snapshot["mcp_url"] != current["mcp_url"]
        or snapshot["fields_sha256"] != current["fields_sha256"]
    ):
        raise MappingError(
            "live Howler fields changed; review a new snapshot and explicitly re-pin the mapping"
        )
    return save_validation(args, token, snapshot, rows_from_file(args.records), post)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url", required=True, help="trusted Howler HTTPS origin, without /api"
    )
    parser.add_argument(
        "--records", required=True, help="generated alert JSONL; never manually edit it"
    )
    parser.add_argument(
        "--fields", required=True, help="pinned get_hit_fields snapshot"
    )
    parser.add_argument(
        "--current-fields",
        required=True,
        help="freshly materialized get_hit_fields snapshot",
    )
    parser.add_argument(
        "--token-file", help="private Howler API token file; alternatively HOWLER_JWT"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    try:
        if any(
            Path(path).resolve() == Path(args.output).resolve()
            for path in (
                args.records,
                args.fields,
                args.current_fields,
                args.token_file,
            )
            if path
        ):
            raise MappingError("output must not overwrite an input or credential file")
        token = (
            Path(args.token_file).read_text().strip()
            if args.token_file
            else os.environ.get("HOWLER_JWT", "").strip()
        )
        if not token:
            raise MappingError(
                "provide a Howler API token through --token-file or HOWLER_JWT"
            )
        summary = run(args, token)
        print(
            json.dumps(
                {
                    "status": "success" if summary["valid"] else "failure",
                    "output_path": args.output,
                    **summary,
                }
            )
        )
        return 0 if summary["valid"] else 1
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, MappingError)
            else f"API/file operation failed ({type(exc).__name__}); no data logged"
        )
        print(json.dumps({"status": "failure", "error": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
