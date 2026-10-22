#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["howler-client==3.2.0"]
# ///
"""File-first CLI around Howler's offline RowMapping/map_rows API.

Mapping syntax, transforms, null handling, and field checks belong to the
released client; this script only handles files, profiling, drafts,
augmentation, and reporting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

from howler_client import MappingError, RowMapping, map_rows


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MappingError("duplicate object key")
        result[key] = value
    return result


def reject_constant(_):
    raise MappingError("non-finite JSON number")


def read_json(path):
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=unique_pairs,
        parse_constant=reject_constant,
    )


def write_file(path, text, replace=False):
    """Atomically write a private artifact without replacing files implicitly."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".howler-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        if replace:
            if path.is_symlink():
                raise MappingError("refusing to replace a symlink")
            os.replace(name, path)
        else:
            try:
                os.link(name, path)
            except FileExistsError:
                raise MappingError(
                    "output exists; use a new path or --replace"
                ) from None
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path, value, replace=False):
    write_file(
        path,
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        replace,
    )


def rows_from_file(path):
    rows = []
    for number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(
                line, object_pairs_hook=unique_pairs, parse_constant=reject_constant
            )
            if not isinstance(row, dict):
                raise TypeError
        except (ValueError, TypeError):
            raise MappingError(f"invalid row object at line {number}") from None
        rows.append(row)
    if not rows:
        raise MappingError("row file is empty")
    return rows


def validate_fields_snapshot(snapshot):
    """Check artifact provenance/integrity, not Howler field types or constraints."""
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "version",
        "mcp_url",
        "fields_sha256",
        "fields",
    }:
        raise MappingError("expected a snapshot produced by mcp_files.py fields")
    if (
        type(snapshot["version"]) is not int
        or snapshot["version"] != 1
        or not isinstance(snapshot["fields"], dict)
        or not snapshot["fields"]
        or not isinstance(snapshot["mcp_url"], str)
        or not snapshot["mcp_url"].startswith("https://")
    ):
        raise MappingError("invalid fields snapshot")
    if snapshot["fields_sha256"] != digest(snapshot["fields"]):
        raise MappingError("fields snapshot fingerprint does not match its contents")
    return snapshot


def fields_from_file(path):
    return validate_fields_snapshot(read_json(path))


def ensure_no_howler_id(record):
    """Network-boundary safeguard for externally supplied alert JSONL.

    RowMapping itself owns the same rule for mapped records. This guard is not a
    replacement for client validation and performs no type or schema validation.
    """
    howler = record.get("howler")
    if any(key == "howler.id" or key.startswith("howler.id.") for key in record) or (
        isinstance(howler, dict)
        and any(key == "id" or key.startswith("id.") for key in howler)
    ):
        raise MappingError("howler.id is server-generated and must not be set")


def compile_mapping(path, snapshot):
    # Do not reinterpret YAML or duplicate the client's mapping validator.
    return RowMapping.from_file(path, fields=snapshot["fields"])


def mapped_batch(compiled, rows):
    records, errors = [], []
    for number, (record, error) in enumerate(map_rows(rows, compiled), 1):
        if error is None:
            records.append(record)
        else:
            # Only private reports contain client diagnostics, never stdout/stderr.
            errors.append({"row": number, "error": str(error)})
    return records, errors


def render(mapping, snapshot, rows):
    """Convenience wrapper; all mapping and validation is delegated to Howler."""
    compiled = RowMapping(mapping, fields=snapshot["fields"])
    records, errors = mapped_batch(compiled, rows)
    if errors:
        raise MappingError("client mapping failed; inspect a private validation report")
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser(
        "inspect", help="profile columns without sample values"
    )
    inspect.add_argument("--rows", required=True)
    init = commands.add_parser("init", help="create an empty client-YAML draft")
    init.add_argument("--on-null", choices=("error", "omit"), default="error")
    add = commands.add_parser("add", help="augment from a saved YAML field fragment")
    add.add_argument("--target", required=True)
    add.add_argument("--spec", required=True)
    add.add_argument("--replace-field", action="store_true")
    for name in ("validate", "render"):
        command = commands.add_parser(name)
        command.add_argument("--rows", required=name == "render")
        if name == "render":
            command.add_argument(
                "--report", help="private client diagnostic/provenance report"
            )
    for name in ("add", "validate", "render"):
        commands.choices[name].add_argument("--mapping", required=True)
        commands.choices[name].add_argument("--fields", required=True)
    for command in commands.choices.values():
        command.add_argument("--output", required=True)
        command.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    inputs = [
        getattr(args, name, None) for name in ("rows", "fields", "mapping", "spec")
    ]
    outputs = [args.output] + ([args.report] if getattr(args, "report", None) else [])
    protected = True
    try:
        resolved = [Path(path).resolve() for path in outputs]
        if len(set(resolved)) != len(resolved):
            raise MappingError("outputs must be different files")
        for output in outputs:
            for name, path in zip(("rows", "fields", "mapping", "spec"), inputs):
                if (
                    path
                    and Path(path).resolve() == Path(output).resolve()
                    and not (
                        args.command == "add"
                        and args.replace
                        and name == "mapping"
                        and output == args.output
                    )
                ):
                    raise MappingError("output must not overwrite an input file")
        protected = False
        for output in outputs:
            path = Path(output)
            if path.is_symlink() or (path.exists() and not args.replace):
                raise MappingError(
                    "output exists or is a symlink; use a new path or --replace"
                )
        if args.command == "inspect":
            rows = rows_from_file(args.rows)
            columns = sorted(set().union(*(row.keys() for row in rows)))
            profile = {
                "row_count": len(rows),
                "columns": {
                    col: {
                        "observed_types": sorted(
                            {
                                type(row[col]).__name__
                                for row in rows
                                if col in row and row[col] is not None
                            }
                        ),
                        "null_count": sum(
                            col in row and row[col] is None for row in rows
                        ),
                        "missing_count": sum(col not in row for row in rows),
                    }
                    for col in columns
                },
            }
            write_json(args.output, profile, args.replace)
        elif args.command == "init":
            # Empty mappings are intentionally drafts, not client-validated mappings.
            write_file(
                args.output,
                yaml.safe_dump(
                    {"version": 1, "on_null": args.on_null, "mappings": {}},
                    sort_keys=False,
                ),
                args.replace,
            )
        else:
            snapshot = fields_from_file(args.fields)
            if args.command == "add":
                # Drafts may be empty; the entire augmented document is validated by
                # RowMapping before it can be saved. No custom YAML loader or schema.
                document = yaml.safe_load(
                    Path(args.mapping).read_text(encoding="utf-8")
                )
                if args.target in document["mappings"] and not args.replace_field:
                    raise MappingError("target already mapped; use --replace-field")
                document["mappings"][args.target] = yaml.safe_load(
                    Path(args.spec).read_text(encoding="utf-8")
                )
                compiled = RowMapping(document, fields=snapshot["fields"])
                write_file(
                    args.output,
                    yaml.safe_dump(
                        compiled.mapping, sort_keys=False, allow_unicode=True
                    ),
                    args.replace,
                )
            else:
                compiled = compile_mapping(args.mapping, snapshot)
                rows = rows_from_file(args.rows) if args.rows else None
                records, errors = (
                    mapped_batch(compiled, rows) if rows is not None else ([], [])
                )
                report = {
                    "valid": not errors,
                    "scope": "local",
                    "engine": "howler-client",
                    "backend_validated": False,
                    "mapping_sha256": digest(compiled.mapping),
                    "mcp_url": snapshot["mcp_url"],
                    "fields_sha256": snapshot["fields_sha256"],
                    "sample_row_count": len(rows) if rows is not None else None,
                    "successful_row_count": len(records) if rows is not None else None,
                    "records_sha256": digest(records)
                    if rows is not None and not errors
                    else None,
                    "output_written": args.command == "render" and not errors,
                    "errors": errors,
                }
                if args.command == "validate":
                    write_json(args.output, report, args.replace)
                else:
                    if not errors:
                        write_file(
                            args.output,
                            "".join(canonical(record) + "\n" for record in records),
                            args.replace,
                        )
                    if args.report:
                        write_json(args.report, report, args.replace)
                if errors:
                    print(
                        json.dumps(
                            {
                                "status": "failure",
                                "error_count": len(errors),
                                "report_path": args.output
                                if args.command == "validate"
                                else args.report,
                            }
                        )
                    )
                    return 1
        print(json.dumps({"status": "success", "output_path": args.output}))
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI boundary must redact third-party errors.
        # Parser/third-party exceptions may contain private values. Keep diagnostics
        # in private reports and only the exception type in terminal summaries.
        message = (
            f"mapping/file operation failed ({type(exc).__name__}); no data logged"
        )
        if args.command == "validate" and not protected:
            try:
                write_json(
                    args.output,
                    {
                        "valid": False,
                        "scope": "local",
                        "engine": "howler-client",
                        "backend_validated": False,
                        "error": str(exc) if isinstance(exc, MappingError) else message,
                    },
                    args.replace,
                )
            except (OSError, MappingError):
                pass
        print(json.dumps({"status": "failure", "error": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
