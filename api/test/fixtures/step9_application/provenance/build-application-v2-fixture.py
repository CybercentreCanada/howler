"""Build application-v2 from origin/main ESCollection saves and the frozen ODM inventory."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_COMMIT = "2da444e40820f3fed8732705d1b378482f4a1218"
EXPECTED_INVENTORY_SHA256 = (
    "60636d74aeb8bdda00684e2bca81f5426b8966a7742770ef4d7612cac9d3f44c"
)
FIXTURE_NAMESPACE = "step9-appverify"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    body = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def rewrite_namespace(value: Any, old: str, new: str) -> Any:
    if isinstance(value, dict):
        return {key: rewrite_namespace(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_namespace(item, old, new) for item in value]
    if isinstance(value, str) and (value == old or value.startswith(old)):
        return new + value[len(old) :]
    return copy.deepcopy(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--inventory-commit", required=True)
    parser.add_argument("--input-fixture", required=True, type=Path)
    parser.add_argument("--captured-documents", required=True, type=Path)
    parser.add_argument("--capture-command", required=True)
    parser.add_argument("--capture-working-directory", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    api_root = args.api_root.resolve(strict=True)
    source_commit = subprocess.run(
        ["git", "-C", str(api_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if (
        source_commit != EXPECTED_SOURCE_COMMIT
        or args.source_commit != EXPECTED_SOURCE_COMMIT
    ):
        raise SystemExit(
            f"Legacy source HEAD mismatch: expected {EXPECTED_SOURCE_COMMIT}, got {source_commit}"
        )

    inventory_path = args.inventory.resolve(strict=True)
    inventory_hash = file_sha256(inventory_path)
    if inventory_hash != EXPECTED_INVENTORY_SHA256:
        raise SystemExit(f"Contract inventory hash mismatch: {inventory_hash}")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    source_seed = json.loads(
        args.input_fixture.resolve(strict=True).read_text(encoding="utf-8")
    )
    captured = json.loads(
        args.captured_documents.resolve(strict=True).read_text(encoding="utf-8")
    )
    collection_names = tuple(source_seed["collections"])
    if set(collection_names) != set(inventory["collections"]) - {"migration"}:
        raise SystemExit(
            "Current fixture and regenerated legacy inventory collection sets differ"
        )
    if set(captured["documents"]) != {"hit", "case", "user"}:
        raise SystemExit(
            "Legacy capture did not return exactly Hit, Case, and User documents"
        )
    if captured["document_counts"] != {"hit": 8, "case": 1, "user": 2}:
        raise SystemExit(
            f"Legacy capture document counts changed: {captured['document_counts']!r}"
        )

    collections: dict[str, Any] = {}
    for name in collection_names:
        contract = inventory["collections"][name]
        old_alias = f"howler-{name}"
        alias = f"{FIXTURE_NAMESPACE}-howler-{name}"
        legacy_index = contract["legacy_index"]
        aliases = legacy_index["aliases"]
        if set(aliases) != {old_alias}:
            raise SystemExit(
                f"Unexpected legacy alias inventory for {name}: {sorted(aliases)}"
            )
        collection: dict[str, Any] = {
            "alias": alias,
            "index_name": f"{alias}_hot",
            "ilm_enabled_by_default": contract["ilm_enabled_by_default"],
            "settings": copy.deepcopy(legacy_index["settings"]),
            "mappings": copy.deepcopy(legacy_index["mappings"]),
            "aliases": {alias: copy.deepcopy(aliases[old_alias])},
        }
        if "ilm_template" in contract:
            collection["historical_ilm_template"] = rewrite_namespace(
                contract["ilm_template"], old_alias, alias
            )
        collections[name] = collection

    metadata = copy.deepcopy(source_seed["metadata"])
    metadata.update(
        {
            "source_inventory": str(
                Path("api/test/unit/odm/fixtures/odm_contract_inventory.json")
            ),
            "source_inventory_sha256": inventory_hash,
            "source_inventory_commit": args.inventory_commit,
            "captured_from_commit": source_commit,
            "collection_contract_source": (
                "current frozen legacy ODM inventory generated from the upstream model contracts"
            ),
            "dynamic_template_order": (
                "copied byte-for-byte from odm_contract_inventory.json; order is semantically significant"
            ),
        }
    )
    capture_metadata = {
        "producer": "origin/main legacy ODM models captured through legacy ESCollection.save",
        "timestamp_format": "legacy default DATEFORMAT",
        "source_postprocessing": [
            "stored source is the exact ESCollection.save JSON body; no source field is removed",
            "model_primitives separates the datastore-generated top-level id from that saved body",
        ],
        "runtime_legacy_imports": False,
        "source_fields": {
            "model_primitives": (
                "exact serialized saved source with only the datastore-generated top-level id separated; "
                "includes __index for Hit and Case"
            ),
            "source": "exact JSON document passed by ESCollection.save to client.index, including id",
        },
        "user_password_safety": source_seed["metadata"]["stored_document_capture"][
            "user_password_safety"
        ],
        "provenance": {
            "source_commit": source_commit,
            "capture_command": args.capture_command,
            "capture_working_directory": args.capture_working_directory,
            "capture_script_sha256": file_sha256(
                Path("/tmp/opencode/step9-wrap/capture-legacy-sources.py")
            ),
            "capture_output_sha256": file_sha256(
                args.captured_documents.resolve(strict=True)
            ),
            "input_fixture_sha256": file_sha256(
                args.input_fixture.resolve(strict=True)
            ),
            "inventory_sha256": inventory_hash,
            "model_primitives_sha256": captured["model_primitives_sha256"],
            "stored_sources_sha256": captured["stored_sources_sha256"],
            "legacy_source_file_sha256": {
                relative: file_sha256(api_root / relative)
                for relative in (
                    "howler/odm/base.py",
                    "howler/odm/models/record.py",
                    "howler/odm/models/case.py",
                    "howler/odm/models/user.py",
                    "howler/datastore/collection.py",
                )
            },
            "fixture_generator_sha256": file_sha256(Path(__file__).resolve()),
            "fixture_generation_command": " ".join([sys.executable, *sys.argv]),
        },
    }
    metadata["stored_document_capture"] = capture_metadata

    documents = copy.deepcopy(captured["documents"])
    fixture = {
        "schema_version": "application-v2",
        "metadata": metadata,
        "collections": collections,
        "documents": documents,
        "test_credentials": copy.deepcopy(source_seed["test_credentials"]),
        "access_fields": copy.deepcopy(source_seed["access_fields"]),
        "query_contracts": copy.deepcopy(source_seed["query_contracts"]),
        "application_verification": copy.deepcopy(
            source_seed["application_verification"]
        ),
        "application_environment": copy.deepcopy(
            source_seed["application_environment"]
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.output.chmod(0o600)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "canonical_sha256": canonical_sha256(fixture),
                "raw_file_sha256": file_sha256(args.output),
                "fixture_version": fixture["schema_version"],
                "source_commit": source_commit,
                "inventory_sha256": inventory_hash,
                "capture_output_sha256": capture_metadata["provenance"][
                    "capture_output_sha256"
                ],
                "model_primitives_sha256": captured["model_primitives_sha256"],
                "stored_sources_sha256": captured["stored_sources_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
