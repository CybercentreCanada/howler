#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["howler-client==3.4.0"]
# ///
"""Ingest a confirmed JSONL file of Howler alerts."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import TextIO
from urllib.parse import urlsplit

from howler_client import get_client


class IngestionError(Exception):
    """Raised when safe ingestion prerequisites are not met."""


def validate_api_url(value: str | None) -> str:
    """Require a trusted HTTPS API base URL without embedded credentials."""
    if not value:
        raise IngestionError

    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise IngestionError

    return value.rstrip("/")


def load_token() -> tuple[str, Path | None]:
    """Read authentication from the configured private token file or environment."""
    token_file = os.environ.get("HOWLER_TOKEN_FILE")
    if token_file:
        path = Path(token_file).resolve(strict=True)
        token = path.read_text(encoding="utf-8").strip()
        if not token:
            raise IngestionError
        return token, path

    token = os.environ.get("HOWLER_JWT", "").strip()
    if not token:
        raise IngestionError
    return token, None


def resolve_paths(
    input_value: str, report_value: str, token_path: Path | None
) -> tuple[Path, Path]:
    """Resolve paths and refuse to overwrite source or credential files."""
    input_path = Path(input_value).resolve(strict=True)
    if not input_path.is_file():
        raise IngestionError

    report_argument = Path(report_value)
    report_path = report_argument.resolve()
    if (
        report_argument.is_symlink()
        or report_path == input_path
        or report_path == token_path
        or report_path.exists()
        or not report_path.parent.is_dir()
    ):
        raise IngestionError

    if token_path == input_path:
        raise IngestionError

    return input_path, report_path


def write_report(handle: TextIO, report: dict[str, object]) -> None:
    """Write a private report to the already-reserved output file."""
    handle.seek(0)
    handle.truncate()
    json.dump(report, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())


def reserve_report(path: Path, report: dict[str, object]) -> TextIO:
    """Create a mode-0600 report exclusively and persist its pending state."""
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    handle = os.fdopen(descriptor, "w+", encoding="utf-8")
    try:
        write_report(handle, report)
    except Exception:
        handle.close()
        path.unlink(missing_ok=True)
        raise
    return handle


def validate_ids(value: object) -> list[str]:
    """Accept only the documented list-of-ID result from the client."""
    if isinstance(value, list) and all(isinstance(alert_id, str) for alert_id in value):
        return value
    raise IngestionError


def main(argv: list[str] | None = None) -> int:
    """Run a single confirmed ingest and write a private result report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", help="trusted Howler HTTPS API URL")
    parser.add_argument("--index", required=True, choices=("hit", "event"))
    parser.add_argument("--input", default="alerts.jsonl", help="alert JSONL file")
    parser.add_argument(
        "--report", default="ingest-report.json", help="new private result report"
    )
    parser.add_argument(
        "--confirm",
        help="exact confirmation value printed by a preview run",
    )
    args = parser.parse_args(argv)

    report_handle = None
    report_path = None
    input_path = None
    api_url = None
    try:
        api_url = validate_api_url(args.api_url or os.environ.get("HOWLER_API_URL"))
        token, token_path = load_token()
        input_path, report_path = resolve_paths(args.input, args.report, token_path)
        base_report: dict[str, object] = {
            "destination": api_url,
            "index": args.index,
            "input": str(input_path),
            "server_returned_count": None,
            "server_returned_ids": None,
        }
        confirmation = f"{api_url}|{args.index}|{input_path}|{report_path}"

        if args.confirm != confirmation:
            print(  # noqa: T201
                json.dumps(
                    {
                        "status": "confirmation_required",
                        **base_report,
                        "report": str(report_path),
                        "confirmation": confirmation,
                    }
                )
            )
            return 2

        pending_report = {
            "status": "pending",
            "outcome_may_be_uncertain": True,
            **base_report,
        }
        report_handle = reserve_report(report_path, pending_report)

        previous_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            client = get_client(
                api_url,
                auth=token,
                retries=1,
                verify=True,
                timeout=120,
                throw_on_bad_request=True,
                throw_on_max_retries=True,
            )
            result = client.v2.ingest.from_file(str(input_path), index=args.index)
        finally:
            logging.disable(previous_disable)

        ids = validate_ids(result)

        write_report(
            report_handle,
            {
                "status": "response_received",
                **base_report,
                "server_returned_count": len(ids),
                "server_returned_ids": ids,
            },
        )
        report_handle.close()
        report_handle = None
        print(  # noqa: T201
            json.dumps(
                {"status": "response_received", "server_returned_count": len(ids)}
            )
        )
        return 0
    except Exception:
        if report_handle is not None:
            with suppress(Exception):
                write_report(
                    report_handle,
                    {
                        "status": "unknown",
                        "outcome_may_be_uncertain": True,
                        "destination": api_url,
                        "index": args.index,
                        "input": str(input_path) if input_path else args.input,
                        "server_returned_count": None,
                        "server_returned_ids": None,
                    },
                )
            with suppress(Exception):
                report_handle.close()

        print(  # noqa: T201
            json.dumps(
                {
                    "status": "failure",
                    "outcome": "unknown",
                    "message": "Ingest failed or returned an unknown result; verify in Howler before any manual rerun.",
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
