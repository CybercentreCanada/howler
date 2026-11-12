"""Capture deterministic sources through origin/main's legacy ESCollection.save path."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from howler.datastore.collection import ESCollection
from howler.odm.models.case import Case
from howler.odm.models.hit import Hit
from howler.odm.models.user import User

MODEL_BY_COLLECTION = {"hit": Hit, "case": Case, "user": User}


class CaptureClient:
    """Capture the serialized request body passed by ESCollection without connecting to ES."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def index(self, **kwargs: Any) -> dict[str, str]:
        self.calls.append(copy.deepcopy(kwargs))
        return {"result": "created"}


class CaptureStore:
    def __init__(self) -> None:
        self.client = CaptureClient()


def canonical_sha256(value: Any) -> str:
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def capture(input_path: Path) -> dict[str, Any]:
    seed = json.loads(input_path.read_text(encoding="utf-8"))
    documents: dict[str, list[dict[str, Any]]] = {}
    ESCollection.IGNORE_ENSURE_COLLECTION = True
    ESCollection.ENSURE_COLLECTION_WARNED = True

    for collection_name, model_type in MODEL_BY_COLLECTION.items():
        store = CaptureStore()
        collection = ESCollection(
            store, collection_name, model_class=model_type, ilm_config=None
        )
        entries = seed["documents"][collection_name]
        captured_entries: list[dict[str, Any]] = []
        for entry in entries:
            document_id = entry["id"]
            model_input = copy.deepcopy(entry["model_primitives"])
            model = model_type(model_input)

            # This is the production model-backed save path. The fake client only intercepts
            # its exact `document=json.dumps(saved_data)` argument; no datastore is contacted.
            collection.save(document_id, model, refresh="false")
            call = store.client.calls[-1]
            if call.get("index") != collection.name or call.get("id") != document_id:
                raise RuntimeError(
                    f"Unexpected save target for {collection_name}/{document_id}"
                )
            source = json.loads(call["document"])
            if source.get("id") != document_id:
                raise RuntimeError(
                    f"Legacy save did not persist id for {collection_name}/{document_id}"
                )

            primitives = copy.deepcopy(source)
            del primitives["id"]
            if collection_name in {"hit", "case"}:
                expected_helper = collection_name
                if primitives.get("__index") != expected_helper:
                    raise RuntimeError(
                        f"Legacy {collection_name} save omitted {expected_helper!r} __index"
                    )
            elif "__index" in primitives:
                raise RuntimeError(
                    f"Legacy {collection_name} unexpectedly emitted __index"
                )

            captured_entries.append(
                {
                    "id": document_id,
                    "model_primitives": primitives,
                    "source": source,
                }
            )
        documents[collection_name] = captured_entries

    flat_documents = [
        {"collection": name, **entry}
        for name, entries in documents.items()
        for entry in entries
    ]
    return {
        "documents": documents,
        "document_counts": {name: len(entries) for name, entries in documents.items()},
        "serialized_document_count": len(flat_documents),
        "model_primitives_sha256": canonical_sha256(
            [
                {
                    "collection": doc["collection"],
                    "id": doc["id"],
                    "model_primitives": doc["model_primitives"],
                }
                for doc in flat_documents
            ]
        ),
        "stored_sources_sha256": canonical_sha256(
            [
                {
                    "collection": doc["collection"],
                    "id": doc["id"],
                    "source": doc["source"],
                }
                for doc in flat_documents
            ]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = capture(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output.chmod(0o600)
    print(
        json.dumps(
            {
                "document_counts": result["document_counts"],
                "serialized_document_count": result["serialized_document_count"],
                "model_primitives_sha256": result["model_primitives_sha256"],
                "stored_sources_sha256": result["stored_sources_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
