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
from pathlib import Path

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
            "target": "tony.stark@gov.com",
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
        "to": {"address": "tony.stark@gov.com"},
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
            "tony.stark@gov.com",
        ],
    },
    "message": (
        "Phishing email received from john.smith@live.ca to tony.stark@gov.com. "
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
        "name": "DESKTOP-TONY01",
    },
    "message": "Process outlook.exe started by explorer.exe on DESKTOP-TONY01.",
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
        "name": "DESKTOP-TONY01",
    },
    "message": (
        "msedge.exe spawned by outlook.exe to open SafeLinks-wrapped phishing URL "
        "on DESKTOP-TONY01."
    ),
}


# ---------------------------------------------------------------------------
# 4. Observables — msedge.exe network connections
# ---------------------------------------------------------------------------
_NETCONN_RAW = [
    # (timestamp, process, dest, dest_port, src_port, sent, rcvd)
    (
        "2026-02-06T17:15:14.677Z",
        "msedge.exe",
        "r8m2dk1w0xq9t5z4-1drvsharepoint.acmedomain.com",
        443,
        49812,
        2602,
        4259,
    ),
    (
        "2026-02-06T17:15:14.695Z",
        "msedge.exe",
        "r8m2dk1w0xq9t5z4-1drvsharepoint.acmedomain.com",
        443,
        49813,
        5189,
        126423,
    ),
    (
        "2026-02-06T17:15:14.844Z",
        "msedge.exe",
        "r8m2dk1w0xq9t5z4-1drvsharepoint.acmedomain.com",
        6080,
        49814,
        721,
        7194,
    ),
    (
        "2026-02-06T17:15:14.922Z",
        "msedge.exe",
        "r8m2dk1w0xq9t5z4-1drvsharepoint.acmedomain.com",
        6080,
        49815,
        2422,
        11582,
    ),
    (
        "2026-02-06T17:15:22.070Z",
        "msedge.exe",
        "r8m2dk1w0xq9t5z4-1drvsharepoint.acmedomain.com",
        6080,
        49816,
        0,
        0,
    ),
    (
        "2026-02-06T17:15:25.785Z",
        "msedge.exe",
        "r8m2dk1w0xq9t5z4-1drvsharepoint.acmedomain.com",
        443,
        49817,
        2026,
        3729,
    ),
    (
        "2026-02-06T17:15:26.372Z",
        "msedge.exe",
        "challenges.cloudflare.com",
        443,
        49818,
        2131,
        21221,
    ),
    (
        "2026-02-06T17:15:26.443Z",
        "msedge.exe",
        "104.18.95.41",
        443,
        49819,
        227048,
        980073,
    ),
    (
        "2026-02-06T17:15:26.496Z",
        "msedge.exe",
        "challenges.cloudflare.com",
        443,
        49820,
        1663,
        3908,
    ),
    (
        "2026-02-06T17:15:26.501Z",
        "msedge.exe",
        "challenges.cloudflare.com",
        443,
        49821,
        2822,
        87304,
    ),
]

NETCONN_OBSERVABLES = [
    {
        "howler": {
            "hash": _hash("observable-netconn", ts, dest, str(dport), str(sport)),
        },
        "timestamp": ts,
        "event": {
            "kind": "event",
            "category": ["network"],
            "type": ["connection"],
        },
        "process": {
            "name": proc,
            "pid": 10212,
        },
        "destination": {
            "domain": dest if not dest[0].isdigit() else None,
            "ip": dest if dest[0].isdigit() else None,
            "port": dport,
            "bytes": rcvd,
        },
        "source": {
            "ip": "10.0.42.15",
            "port": sport,
            "bytes": sent,
        },
        "host": {
            "name": "DESKTOP-TONY01",
        },
        "message": (
            f"{proc} (PID 10212) 10.0.42.15:{sport} -> {dest}:{dport}  sent={sent} rcvd={rcvd}"
        ),
    }
    for ts, proc, dest, dport, sport, sent, rcvd in _NETCONN_RAW
]


# ---------------------------------------------------------------------------
# 5. Observable — Entra ID sign-in attempt (AADSTS50074 – MFA required)
# ---------------------------------------------------------------------------
ENTRA_SIGNIN_OBSERVABLE = {
    "howler": {
        "hash": _hash("observable-entra-signin-demo"),
    },
    "timestamp": "2026-02-06T16:11:37.139Z",
    "event": {
        "kind": "event",
        "category": ["authentication"],
        "type": ["start"],
        "outcome": "failure",
        "code": "AADSTS50074",
        "reason": "MFA required",
    },
    "source": {
        "ip": "2411:5378:12:1260::1",
    },
    "organization": {
        "name": "government.com",
    },
    "user": {
        "email": "Tony.Stark@gov.com",
    },
    "user_agent": {
        "original": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Edg/111.0.1661.44 "
            "Safari/537.36"
        ),
    },
    "observer": {
        "product": "Azure Active Directory",
        "name": "Microsoft.O365.Management.Audit.AzureActiveDirectoryStsLogon",
    },
    "labels": {
        "app_id": "a91a48ee-7c1c-404b-9360-dd7dfdaa6094",
        "response_code": "AADSTS50074",
    },
    "host": {
        "name": "DESKTOP-TONY01",
    },
    "message": (
        "Entra ID sign-in failure for Tony.Stark@gov.com from 2411:5378:12:1260::1. "
        "Response: AADSTS50074 – MFA required. "
        "Log source: Microsoft.O365.Management.Audit.AzureActiveDirectoryStsLogon. "
        "App ID: a91a48ee-7c1c-404b-9360-dd7dfdaa6094."
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
    """Create a single case via POST /api/v2/case/.

    The case_data dict may include an 'items' list, each with
    'type', 'value', and optional 'path'. Items are linked to the
    case automatically during creation by the service layer.
    """
    result = _post("/api/v2/case/", case_data)
    return result.get("api_response", result)


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

    # --- Ingest network connection observables ---
    print("[3/5] Creating network connection observables...")
    netconn_ids = ingest_observables(NETCONN_OBSERVABLES)
    if not netconn_ids:
        print("  [WARN] Failed to create network observables.", file=sys.stderr)
    for nc_id, (ts, _proc, dest, dport, _sport, sent, rcvd) in zip(
        netconn_ids, _NETCONN_RAW
    ):
        print(f"  Connection {dest}:{dport} (sent={sent}/rcvd={rcvd}): {nc_id}")

    # --- Ingest Entra ID sign-in observable ---
    print("[4/6] Creating Entra ID sign-in observable...")
    signin_ids = ingest_observables([ENTRA_SIGNIN_OBSERVABLE])
    if not signin_ids:
        print("  [WARN] Failed to create sign-in observable.", file=sys.stderr)
    signin_obs_id = signin_ids[0] if signin_ids else None
    if signin_obs_id:
        print(f"  Sign-in (AADSTS50074): {signin_obs_id}")

    # --- Create the case (with items linked inline) ---
    print("[5/6] Creating investigation case with linked items...")
    overview_path = Path(__file__).resolve().parent.parent.parent / "overview.md"
    overview_content = (
        overview_path.read_text(encoding="utf-8") if overview_path.exists() else ""
    )
    case_payload = {
        "title": "Phishing – John Smith Law Corporation",
        "summary": (
            "Investigate phishing email from john.smith@live.ca targeting "
            "tony.stark@gov.com. Email contained a suspicious link to "
            "sharefile08.s3.us-east-1.amazonaws.com. Outlook.exe opened the link "
            "via msedge.exe on DESKTOP-TONY01."
        ),
        "overview": overview_content,
        "items": [
            {
                "type": "hit",
                "value": hit_id,
                "path": f"alerts/Email Gateway ({hit_id})",
            },
            {
                "type": "observable",
                "value": outlook_obs_id,
                "path": f"observables/outlook.exe ({outlook_obs_id})",
            },
            {
                "type": "observable",
                "value": edge_obs_id,
                "path": f"observables/msedge.exe ({edge_obs_id})",
            },
            *[
                {
                    "type": "observable",
                    "value": nc_id,
                    "path": f"observables/network/{dest}:{port} ({nc_id})",
                }
                for nc_id, (_ts, _p, dest, port, _sp, _s, _r) in zip(
                    netconn_ids, _NETCONN_RAW
                )
            ],
            *(
                [
                    {
                        "type": "observable",
                        "value": signin_obs_id,
                        "path": f"observables/Entra ID Sign-in ({signin_obs_id})",
                    }
                ]
                if signin_obs_id
                else []
            ),
        ],
    }
    case_result = create_case(case_payload)
    case_id = case_result.get("case_id")
    if not case_id:
        print(f"  Unexpected response: {case_result}", file=sys.stderr)
        sys.exit(1)
    print(f"  Case created: {case_id}")
    print(f"  Linked hit {hit_id}")
    print(f"  Linked observable {outlook_obs_id}")
    print(f"  Linked observable {edge_obs_id}")
    for nc_id in netconn_ids:
        print(f"  Linked network observable {nc_id}")
    if signin_obs_id:
        print(f"  Linked Entra sign-in observable {signin_obs_id}")

    # --- Add investigation tasks ---
    print("[6/6] Adding investigation tasks...")
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
            "summary": "Review process telemetry on DESKTOP-TONY01 for further suspicious activity.",
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
            "summary": "Notify tony.stark@gov.com about the phishing email.",
        },
    ]
    update_case(case_id, {"tasks": tasks})
    for t in tasks:
        print(f"  Task [{t['assignment']}]: {t['summary'][:60]}...")

    print(f"\n=== Done! Case ID: {case_id} ===")
