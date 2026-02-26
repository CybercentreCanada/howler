"""
Demo ingestion script for Howler.

Creates a phishing investigation case with:
  - Hit:        Suspicious email from john.smith@live.ca
  - Observable: outlook.exe process spawned from explorer.exe
  - Observable: msedge.exe spawned from outlook.exe opening the phishing link

Then creates a case tying them all together.

Usage:
    python create_case.py

Set HOWLER_SERVER env var to override the default (http://localhost:5000).
"""

import base64
import hashlib
import os
import sys
import uuid

import requests

# ---------------------------------------------------------------------------
# Configuration – uses the admin devkey created by random_data.create_users()
# Auth format: "user:apikey_name:apikey_password"
# ---------------------------------------------------------------------------
HOWLER_SERVER = os.environ.get("HOWLER_SERVER", "http://localhost:5000")
API_KEY_USER = "admin"
API_KEY = "devkey:admin"

_credentials = base64.b64encode(f"{API_KEY_USER}:{API_KEY}".encode("utf-8")).decode(
    "utf-8"
)

HEADERS = {
    "Authorization": f"Basic {_credentials}",
    "Content-Type": "application/json",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash(*parts: str) -> str:
    """Deterministic 64-char hex hash so re-runs are idempotent."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _post(path: str, payload):
    """POST JSON to the Howler API and return the parsed response."""
    url = f"{HOWLER_SERVER}{path}"
    resp = requests.post(url, json=payload, headers=HEADERS)
    if not resp.ok:
        print(f"  [ERROR] {resp.status_code} {resp.text}", file=sys.stderr)
    resp.raise_for_status()
    return resp.json()


def _put(path: str, payload):
    """PUT JSON to the Howler API and return the parsed response."""
    url = f"{HOWLER_SERVER}{path}"
    resp = requests.put(url, json=payload, headers=HEADERS)
    if not resp.ok:
        print(f"  [ERROR] {resp.status_code} {resp.text}", file=sys.stderr)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# 1. Hit — Phishing email received
# ---------------------------------------------------------------------------
PHISHING_HIT = {
    "howler": {
        "analytic": "Email Gateway",
        "detection": "Suspicious Inbound Email",
        "hash": _hash("phishing-email-hit-demo"),
        "outline": {
            "threat": "john.smith@live.ca",
            "target": "elvis.presley@gov.com",
            "indicators": [
                "john.smith@live.ca",
                "sharefile08.s3.us-east-1.amazonaws.com",
            ],
            "summary": (
                "Phishing email from john.smith@live.ca (subject: John Smith Law Corporation) "
                "containing a suspicious link to sharefile08.s3.us-east-1.amazonaws.com."
            ),
        },
    },
    "event": {
        "kind": "alert",
        "category": ["email"],
        "type": ["info"],
    },
    "email": {
        "from": {"address": "john.smith@live.ca"},
        "to": {"address": "elvis.presley@gov.com"},
        "cc": {"address": "tony.stark@gov.com"},
        "subject": "John Smith Law Corporation",
        "direction": "inbound",
    },
    "url": {
        "full": "https://sharefile08.s3.us-east-1.amazonaws.com/document20251021_0101001.html",
        "domain": "sharefile08.s3.us-east-1.amazonaws.com",
        "scheme": "https",
        "path": "/document20251021_0101001.html",
    },
    "related": {
        "user": [
            "elvis.presley@gov.com",
            "tony.stark@gov.com",
            "benny.ben@gov.com",
            "gennie.gen@gov.com",
        ],
    },
    "message": (
        "Phishing email received from john.smith@live.ca to multiple gov.com recipients. "
        "Subject: 'John Smith Law Corporation'. "
        "Contains link: https://sharefile08.s3.us-east-1.amazonaws.com/document20251021_0101001.html"
    ),
}

# ---------------------------------------------------------------------------
# 2. Observable — outlook.exe launched from explorer.exe
# ---------------------------------------------------------------------------
OUTLOOK_OBSERVABLE = {
    "howler": {
        "hash": _hash("observable-outlook-demo"),
    },
    "event": {
        "kind": "event",
        "category": ["process"],
        "type": ["start"],
    },
    "process": {
        "name": "outlook.exe",
        "executable": "C:\\Program Files (x86)\\Microsoft Office\\root\\Office16\\OUTLOOK.exe",
        "command_line": (
            '"C:\\Program Files (x86)\\Microsoft Office\\root\\Office16\\OUTLOOK.exe"'
        ),
        "pid": 7344,
        "parent": {
            "name": "explorer.exe",
            "executable": "C:\\Windows\\explorer.exe",
            "pid": 2140,
        },
    },
    "host": {
        "name": "DESKTOP-ELVIS01",
    },
    "message": "Process outlook.exe started by explorer.exe on DESKTOP-ELVIS01.",
}

# ---------------------------------------------------------------------------
# 3. Observable — msedge.exe launched by outlook.exe to open phishing link
# ---------------------------------------------------------------------------
EDGE_OBSERVABLE = {
    "howler": {
        "hash": _hash("observable-msedge-demo"),
    },
    "event": {
        "kind": "event",
        "category": ["process"],
        "type": ["start"],
    },
    "process": {
        "name": "msedge.exe",
        "executable": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "command_line": (
            '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" '
            "--single-argument "
            "microsoftedge:///?url=https%3A%2F%2Fcan01.safelinks.protection.outlook.com"
            "%2F%3Furl%3Dhttps%253A%252F%252Fsharefile08.s3.us-east-1.amazonaws.com"
            "%252Fdocument20251021_0101001.html"
        ),
        "pid": 10212,
        "parent": {
            "name": "outlook.exe",
            "executable": "C:\\Program Files (x86)\\Microsoft Office\\root\\Office16\\OUTLOOK.exe",
            "pid": 7344,
        },
    },
    "url": {
        "full": "https://sharefile08.s3.us-east-1.amazonaws.com/document20251021_0101001.html",
        "domain": "sharefile08.s3.us-east-1.amazonaws.com",
        "scheme": "https",
        "path": "/document20251021_0101001.html",
    },
    "host": {
        "name": "DESKTOP-ELVIS01",
    },
    "message": (
        "msedge.exe spawned by outlook.exe to open SafeLinks-wrapped phishing URL "
        "on DESKTOP-ELVIS01."
    ),
}


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def ingest_hits(hits: list[dict]) -> list[str]:
    """Create hits via POST /api/v1/hit/ and return their IDs."""
    result = _post("/api/v1/hit/", hits)
    api = result.get("api_response", result)
    valid = api.get("valid", [])
    invalid = api.get("invalid", [])
    ids = [h["howler"]["id"] for h in valid]
    if invalid:
        print(f"  [WARN] {len(invalid)} invalid hit(s):", file=sys.stderr)
        for inv in invalid:
            print(f"    - {inv['error']}", file=sys.stderr)
    return ids


def ingest_observables(observables: list[dict]) -> list[str]:
    """Create observables via POST /api/v2/ingest/observable and return their IDs."""
    result = _post("/api/v2/ingest/observable", observables)
    api = result.get("api_response", result)
    # api_response is a list of IDs
    if isinstance(api, list):
        return api
    ids = api.get("ids", []) if isinstance(api, dict) else []
    return ids


def create_case(case_data: dict) -> dict:
    """Create a single case via POST /api/v2/case/."""
    result = _post("/api/v2/case/", case_data)
    return result.get("api_response", result)


def append_case_item(case_id: str, item: dict) -> None:
    """Append an item to an existing case."""
    _post(f"/api/v2/case/{case_id}/items", item)


def update_case(case_id: str, data: dict) -> dict:
    """Update a case via PUT /api/v2/case/<id>."""
    result = _put(f"/api/v2/case/{case_id}", data)
    return result.get("api_response", result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Howler Demo Ingestion ===\n")

    # --- Ingest the phishing email hit ---
    print("[1/5] Creating phishing email hit...")
    hit_ids = ingest_hits([PHISHING_HIT])
    if not hit_ids:
        print("  Failed to create hit. Aborting.", file=sys.stderr)
        sys.exit(1)
    hit_id = hit_ids[0]
    print(f"  Hit created: {hit_id}")

    # --- Ingest the two process observables ---
    print("[2/5] Creating process observables...")
    obs_ids = ingest_observables([OUTLOOK_OBSERVABLE, EDGE_OBSERVABLE])
    if len(obs_ids) < 2:
        print("  Failed to create process observables. Aborting.", file=sys.stderr)
        sys.exit(1)
    outlook_obs_id, edge_obs_id = obs_ids[0], obs_ids[1]
    print(f"  Observable (outlook.exe): {outlook_obs_id}")
    print(f"  Observable (msedge.exe):  {edge_obs_id}")

    # --- Create the case ---
    print("[3/5] Creating investigation case...")
    case_payload = {
        "title": "Phishing – John Smith Law Corporation",
        "summary": (
            "Investigate phishing email from john.smith@live.ca targeting multiple "
            "gov.com recipients. Email contained a suspicious link to "
            "sharefile08.s3.us-east-1.amazonaws.com. Outlook.exe opened the link "
            "via msedge.exe on DESKTOP-ELVIS01."
        ),
    }
    case_result = create_case(case_payload)
    case_id = case_result.get("case_id")
    if not case_id:
        print(f"  Unexpected response: {case_result}", file=sys.stderr)
        sys.exit(1)
    print(f"  Case created: {case_id}")

    # --- Add investigation tasks ---
    print("[4/5] Adding investigation tasks...")
    tasks = [
        {
            "id": str(uuid.uuid4()),
            "assignment": "goose",
            "summary": "Analyze phishing email headers and extract IOCs.",
            "path": f"alerts/Email Gateway ({hit_id})",
        },
        {
            "id": str(uuid.uuid4()),
            "assignment": "huey",
            "summary": "Review process telemetry on DESKTOP-ELVIS01 for further suspicious activity.",
            "path": f"observables/outlook.exe ({outlook_obs_id})",
        },
        {
            "id": str(uuid.uuid4()),
            "assignment": "huey",
            "summary": "Determine if credentials were entered on the phishing page opened by msedge.exe.",
            "path": f"observables/msedge.exe ({edge_obs_id})",
        },
        {
            "id": str(uuid.uuid4()),
            "assignment": "goose",
            "summary": "Block sharefile08.s3.us-east-1.amazonaws.com at the proxy/firewall.",
        },
        {
            "id": str(uuid.uuid4()),
            "assignment": "goose",
            "summary": "Notify affected recipients (elvis.presley, tony.stark, benny.ben, gennie.gen) about the phishing email.",
        },
    ]
    update_case(case_id, {"tasks": tasks})
    for t in tasks:
        print(f"  Task [{t['assignment']}]: {t['summary'][:60]}...")

    # --- Link items to the case ---
    print("[5/5] Linking hits and observables to case...")

    append_case_item(
        case_id,
        {
            "type": "hit",
            "value": hit_id,
            "path": f"alerts/Email Gateway ({hit_id})",
        },
    )
    print(f"  Linked hit {hit_id}")

    append_case_item(
        case_id,
        {
            "type": "observable",
            "value": outlook_obs_id,
            "path": f"observables/outlook.exe ({outlook_obs_id})",
        },
    )
    print(f"  Linked observable {outlook_obs_id}")

    append_case_item(
        case_id,
        {
            "type": "observable",
            "value": edge_obs_id,
            "path": f"observables/msedge.exe ({edge_obs_id})",
        },
    )
    print(f"  Linked observable {edge_obs_id}")

    print(f"\n=== Done! Case ID: {case_id} ===")
