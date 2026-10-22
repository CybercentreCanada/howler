#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["howler-client==3.2.0", "mcp>=1.26,<2", "httpx>=0.28,<1"]
# ///
"""Materialize target metadata returned by the Howler MCP get_hit_fields tool."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from mapping import (
    MappingError,
    digest,
    reject_constant,
    unique_pairs,
    validate_fields_snapshot,
    write_json,
)


def tool_data(result):
    if result.isError:
        # MCP errors can contain private information. Keep details out of terminal output.
        raise MappingError(
            "MCP tool failed; check the selected endpoint and supplied credentials"
        )
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    texts = [
        block.text for block in result.content if getattr(block, "type", None) == "text"
    ]
    if len(texts) != 1:
        raise MappingError("expected one JSON tool response")
    try:
        return json.loads(
            texts[0], object_pairs_hook=unique_pairs, parse_constant=reject_constant
        )
    except ValueError:
        raise MappingError("MCP response was not JSON") from None


async def call_tool(endpoint, token, name, arguments):
    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    # Never forward a bearer credential to a redirect target.
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False,
        timeout=120,
    ) as client:
        async with streamable_http_client(endpoint, http_client=client) as (
            reader,
            writer,
            _,
        ):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                return tool_data(await session.call_tool(name, arguments))


def check_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.query
    ):
        raise MappingError(
            "MCP URL must be HTTPS without credentials, query, or fragment"
        )


async def run(args, token, call=None):
    check_endpoint(args.mcp_url)
    if call is None:
        call = call_tool
    fields = await call(args.mcp_url, token, "get_hit_fields", {})
    if not isinstance(fields, dict) or not fields:
        raise MappingError("get_hit_fields returned an empty or unsupported response")
    snapshot = {
        "version": 1,
        "mcp_url": args.mcp_url,
        "fields_sha256": digest(fields),
        "fields": fields,
    }
    validate_fields_snapshot(snapshot)
    write_json(args.output, snapshot, args.replace)
    return {"field_count": len(fields)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fields = commands.add_parser(
        "fields", help="materialize get_hit_fields as a snapshot"
    )
    fields.add_argument(
        "--mcp-url", required=True, help="selected Howler MCP HTTPS endpoint"
    )
    fields.add_argument(
        "--token-file", help="private token file; alternatively HOWLER_JWT"
    )
    fields.add_argument("--output", required=True)
    fields.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    try:
        if (
            args.token_file
            and Path(args.token_file).resolve() == Path(args.output).resolve()
        ):
            raise MappingError("output must not overwrite the supplied credential file")
        token = (
            Path(args.token_file).read_text().strip()
            if args.token_file
            else os.environ.get("HOWLER_JWT", "").strip()
        )
        if not token:
            raise MappingError("provide a token with --token-file or HOWLER_JWT")
        summary = asyncio.run(run(args, token))
        print(json.dumps({"status": "success", "output_path": args.output, **summary}))
        return 0
    except Exception as exc:
        message = (
            str(exc)
            if isinstance(exc, MappingError)
            else f"MCP/file operation failed ({type(exc).__name__}); no data logged"
        )
        print(json.dumps({"status": "failure", "error": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
