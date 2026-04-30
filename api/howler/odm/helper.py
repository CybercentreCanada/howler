import json
import random
from datetime import datetime, timedelta
from hashlib import md5
from math import ceil
from random import choice, randint, sample
from typing import Any, cast

from howler.common.logging import get_logger
from howler.config import CLASSIFICATION, config
from howler.datastore.howler_store import HowlerDatastore
from howler.helper.discover import get_apps_list
from howler.odm.base import Model
from howler.odm.constants import Status
from howler.odm.models.case import Case, CaseItem, CaseRule, CaseTask
from howler.odm.models.dossier import Dossier
from howler.odm.models.event import Event
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Escalation, Link
from howler.odm.models.lead import Lead
from howler.odm.models.pivot import Pivot
from howler.odm.models.user import User
from howler.odm.randomizer import (
    get_random_filename,
    get_random_host,
    get_random_ip,
    get_random_user_agent,
    get_random_word,
    random_department,
    random_model_obj,
)
from howler.plugins import get_plugins
from howler.security.utils import get_password_hash
from howler.services import case_service
from howler.utils.constants import TESTING
from howler.utils.uid import get_random_id

APPS = get_apps_list()
ESCALATIONS = Escalation.list()
EXAMPLE_ANALYTICS = ["Password Checker", "Bad Guy Finder", "Exploit Patcher"]

logger = get_logger(__file__)


def generate_useful_hit(  # noqa: C901
    lookups: dict[str, dict[str, Any]],
    users: list[str],
    prune_hit: bool = True,
    hit_ids: list[str] | None = None,
    event_ids: list[str] | None = None,
) -> Hit:
    "Create a random, useful/cogent hit for synthetic data"
    hit: Hit = random_model_obj(cast(Model, Hit))

    if CLASSIFICATION.enforce:
        hit.classification = CLASSIFICATION.UNRESTRICTED

    rand_seed = random.random()

    timestamp = datetime.now() - timedelta(
        days=round(rand_seed * 30),
        hours=min(max(round(random.gauss(14, 3)), 0), 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

    hit.event.created = timestamp.isoformat() + "Z"
    hit.event.provider = choice(["HBS", "NBS", "CBS", "AssemblyLine"])
    hit.timestamp = timestamp.isoformat() + "Z"

    hit.organization.name, hit.organization.id = random_department()
    hit.threat.framework = choice(["MITRE ATT&CK", "Custom"])
    tactic_id = choice(
        [
            *list(lookups.get("tactics", {}).keys()),
            *[icon for icon in lookups["icons"] if icon.startswith("TA")],
        ]
    )
    technique_id = choice(
        [
            *list(lookups.get("techniques", {}).keys()),
            *[icon for icon in lookups["icons"] if not icon.startswith("TA")],
        ]
    )
    hit.threat.tactic.id = tactic_id
    hit.threat.tactic.name = lookups.get("tactics", {}).get(tactic_id, {}).get("name", "Unknown")
    hit.threat.technique.id = technique_id
    hit.threat.technique.name = lookups.get("techniques", {}).get(technique_id, {}).get("name", "Unknown")
    hit.howler.outline.threat = get_random_ip()
    hit.howler.outline.target = get_random_host()
    hit.howler.outline.indicators = []
    for _ in range(round(rand_seed * 12)):
        ind_type = choice(["ip", "file", "department", "user_agent"])
        if ind_type == "ip":
            hit.howler.outline.indicators.append(get_random_ip())
        elif ind_type == "file":
            hit.howler.outline.indicators.append(get_random_filename())
        elif ind_type == "department":
            hit.howler.outline.indicators.append(random_department()[0])
        elif ind_type == "user_agent":
            hit.howler.outline.indicators.append(get_random_user_agent())

    hit.cloud.service.name = choice(
        [
            "Azure",
            "Amazon AWS",
            "Office365",
            "Google Drive",
            "Google Docs",
            "Microsoft Teams",
        ]
    )
    hit.aws.account.id = get_random_id()
    hit.aws.organization.id = get_random_id()
    hit.azure.subscription_id = get_random_id()
    hit.azure.tenant_id = get_random_id()
    hit.azure.resource_id = get_random_id()
    hit.gcp.project_id = get_random_id()
    hit.gcp.network_id = get_random_id()
    hit.gcp.service_account_id = get_random_id()
    hit.gcp.resource_id = get_random_id()
    hit.user.name = get_random_word()
    hit.user_agent.original = get_random_user_agent()
    hit.howler.analytic = choice(EXAMPLE_ANALYTICS)
    hit.howler.detection = hit.threat.tactic.name

    for i in range(len(hit.howler.comment)):
        hit.howler.comment[i].user = choice(users)

    hit.howler.labels.assignments = sample(
        [
            "APA2B",
            "CCID1A",
            "ACE1C",
            "APA1B",
            "ADS4B",
            "ADS2A",
        ],
        1,
    )

    hit.howler.labels.generic = sample(
        [
            "Outlook",
            "Danger",
            "Drive",
            "Documentation",
            "Super Teams",
        ],
        ceil(rand_seed * 2),
    )

    hit.howler.labels.campaign = []
    hit.howler.labels.insight = []
    hit.howler.labels.victim = []
    hit.howler.labels.mitigation = []
    hit.howler.labels.operation = []
    hit.howler.labels.threat = []
    hit.howler.labels.tuning = []

    label_type = ceil(rand_seed * 7)
    if label_type == 1:
        hit.howler.labels.campaign = ["Bad event 2023-07"]
    elif label_type == 2:
        hit.howler.labels.insight = ["admin"]
    elif label_type == 3:
        hit.howler.labels.victim = ["Bobby's Ice-Cream"]
    elif label_type == 4:
        hit.howler.labels.mitigation = ["Blocked: google.com"]
    elif label_type == 5:
        hit.howler.labels.operation = ["OP_HOWLER"]
    elif label_type == 6:
        hit.howler.labels.tuning = ["Tune example"]
    else:
        hit.howler.labels.threat = ["Bad Mojo"]

    hit.event.id = hit.howler.id

    hit.howler.assessment = None
    hit.howler.rationale = None
    hit.howler.triaged = None
    hit.howler.status = "open"
    hit.howler.assignment = "unassigned"
    hit.howler.escalation = choice([Escalation.HIT, Escalation.ALERT])

    if randint(1, 10) > 9:
        hit.howler.expiry = datetime.now() + timedelta(days=randint(1, 60))
    else:
        hit.howler.expiry = None

    hit.howler.outline.threat = choice(
        [
            hit.howler.outline.threat,
            hit.howler.outline.threat,
            hit.howler.outline.threat,
            f"{md5(hit.howler.outline.threat.encode()).hexdigest()}-thing.baduser.org",  # noqa: S324
        ]
    )

    hit.howler.outline.target = choice(
        [
            hit.howler.outline.target,
            hit.howler.outline.target,
            hit.howler.outline.target,
            f"{md5(hit.howler.outline.target.encode()).hexdigest()}.gc.ca",  # noqa: S324
        ]
    )

    hit.howler.data = [
        json.dumps(
            {
                "key": "value",
                "boolean": True,
                "number": 5,
                "float": 10.456,
                "array": ["a", "b", "c"],
            }
        ),
        json.dumps({"key": "value1", "boolean": False, "number": 34, "float": 10678.098}),
        "not json just a string",
        json.dumps(
            {
                "KQLQuery": (
                    "\n    let ioc_lookBack = 14d;\n    let deviceActionAllowed = datatable (action:string) [\n"
                    'NetworkIP\n    | parse kind=regex flags = U SourceZoneURI_CF with * "[\\\\s\\\\S-]+/" Department '
                    "summarize Summary=make_list(Source_Overview) by Indicator\n"
                ),
            }
        ),
    ]

    hit.howler.links = [
        Link(
            {
                "title": "Goose",
                "href": "https://en.wikipedia.org/wiki/Canada_goose",
                "icon": (
                    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Canada_goose_on_Seedskadee_NWR"
                    "_%2827826185489%29.jpg/788px-Canada_goose_on_Seedskadee_NWR_%2827826185489%29.jpg"
                ),
            }
        )
    ]

    try:
        hit.howler.links.extend(
            Link(
                {
                    "title": get_random_word(),
                    "href": app["route"],
                    "icon": app["name"],
                }
            )
            for app in random.choices(APPS, k=5)
        )
    except IndexError:
        pass

    hit.howler.dossier = [
        Lead(
            {
                "icon": "material-symbols:sound-detection-dog-barking",
                "label": {"en": "Example Lead", "fr": "Exemple d'un lead"},
                "format": "markdown",
                "content": "# Hello, World!\n\nThis is a snippet of markdown to show off an example lead.",
            }
        ),
    ]

    if config.core.clue.enabled:
        hit.howler.dossier.append(
            Lead(
                {
                    "icon": "material-symbols:image",
                    "label": {"en": "Clue", "fr": "Clue"},
                    "format": "clue",
                    "content": "test-plugin.image",
                    "metadata": {"type": "ip", "value": "127.0.01", "classification": "TLP:CLEAR"},
                }
            )
        )

        hit.howler.dossier.append(
            Lead(
                {
                    "icon": "material-symbols:code-rounded",
                    "label": {"en": "Clue", "fr": "Clue"},
                    "format": "clue",
                    "content": "test-plugin.json",
                    "metadata": {"type": "ip", "value": "127.0.01", "classification": "TLP:CLEAR"},
                }
            )
        )

    for log in hit.howler.log:
        log.previous_version = get_random_id()

    new_keys: list[str] = []
    for plugin in get_plugins():  # pragma: no cover
        if generate := plugin.modules.odm.generation.get("hit", None):
            _new_keys, hit = generate(hit)
            new_keys += _new_keys

    if len(new_keys) > 0:
        logger.debug("%s new top-level fields configured")

    if prune_hit:
        empty_hit = Hit({"howler": hit.howler})

        for key in hit.fields():
            if key in [
                "howler",
                "event",
                "related",
                "organization",
                "threat",
                "timestamp",
            ]:
                continue

            if key in new_keys:
                continue

            if hit.howler.analytic.lower() != "assemblyline":
                hit.assemblyline = None
            else:
                verdict = choice(["info", "malicious", "safe", "suspicious"])
                for host in hit.assemblyline.antivirus:
                    host.verdict = verdict
                for host in hit.assemblyline.behaviour:
                    host.verdict = verdict
                for host in hit.assemblyline.heuristic:
                    host.verdict = verdict
                for host in hit.assemblyline.yara:
                    host.verdict = verdict
                for host in hit.assemblyline.attribution:
                    host.verdict = verdict
                for item in hit.assemblyline.mitre.tactic:
                    item.verdict = verdict
                for item in hit.assemblyline.mitre.technique:
                    item.verdict = verdict

                if key in ["related", "file"]:
                    continue

            if round(rand_seed * 4) < 3:
                hit[key] = empty_hit[key]

    related: list[str] = []
    if hit_ids:
        related.extend(sample(hit_ids, k=randint(0, min(3, len(hit_ids)))))
    if event_ids:
        related.extend(sample(event_ids, k=randint(0, min(5, len(event_ids)))))
    hit.howler.related = related

    return hit


def generate_useful_event(  # noqa: C901
    lookups: dict[str, dict[str, Any]], users: list[str], prune: bool = True
) -> Event:
    "Create a random, useful/cogent event for synthetic data"
    event: Event = random_model_obj(cast(Model, Event))

    rand_seed = random.random()

    timestamp = datetime.now() - timedelta(
        days=round(rand_seed * 30),
        hours=min(max(round(random.gauss(14, 3)), 0), 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )

    event.event.created = timestamp.isoformat() + "Z"
    event.event.provider = choice(["HBS", "NBS", "CBS", "AssemblyLine"])
    event.timestamp = timestamp.isoformat() + "Z"

    event.organization.name, event.organization.id = random_department()
    event.threat.framework = choice(["MITRE ATT&CK", "Custom"])
    tactic_id = choice(
        [
            *list(lookups.get("tactics", {}).keys()),
            *[icon for icon in lookups["icons"] if icon.startswith("TA")],
        ]
    )
    technique_id = choice(
        [
            *list(lookups.get("techniques", {}).keys()),
            *[icon for icon in lookups["icons"] if not icon.startswith("TA")],
        ]
    )
    event.threat.tactic.id = tactic_id
    event.threat.tactic.name = lookups.get("tactics", {}).get(tactic_id, {}).get("name", "Unknown")
    event.threat.technique.id = technique_id
    event.threat.technique.name = lookups.get("techniques", {}).get(technique_id, {}).get("name", "Unknown")

    event.cloud.service.name = choice(
        [
            "Azure",
            "Amazon AWS",
            "Office365",
            "Google Drive",
            "Google Docs",
            "Microsoft Teams",
        ]
    )
    event.aws.account.id = get_random_id()
    event.aws.organization.id = get_random_id()
    event.azure.subscription_id = get_random_id()
    event.azure.tenant_id = get_random_id()
    event.azure.resource_id = get_random_id()
    event.gcp.project_id = get_random_id()
    event.gcp.network_id = get_random_id()
    event.gcp.service_account_id = get_random_id()
    event.gcp.resource_id = get_random_id()
    event.user.name = get_random_word()
    event.user_agent.original = get_random_user_agent()

    for i in range(len(event.howler.comment)):
        event.howler.comment[i].user = choice(users)

    event.event.id = event.howler.id

    event.howler.escalation = choice([Escalation.HIT, Escalation.ALERT])

    if randint(1, 10) > 9:
        event.howler.expiry = datetime.now() + timedelta(days=randint(1, 60))
    else:
        event.howler.expiry = None

    event.howler.data = [
        json.dumps(
            {
                "key": "value",
                "boolean": True,
                "number": 5,
                "float": 10.456,
                "array": ["a", "b", "c"],
            }
        ),
        json.dumps({"key": "value1", "boolean": False, "number": 34, "float": 10678.098}),
        "not json just a string",
        json.dumps(
            {
                "KQLQuery": (
                    "\n    let ioc_lookBack = 14d;\n    let deviceActionAllowed = datatable (action:string) [\n"
                    'NetworkIP\n    | parse kind=regex flags = U SourceZoneURI_CF with * "[\\\\s\\\\S-]+/" Department '
                    "summarize Summary=make_list(Source_Overview) by Indicator\n"
                ),
            }
        ),
    ]

    return event


def create_users_with_username(ds: HowlerDatastore, usernames: list[str]):
    """Create basic users with username and password for testing puposes"""
    for username in usernames:
        user_data = User(
            {
                "name": f"{username}",
                "email": f"{username}@howler.cyber.gc.ca",
                "apikeys": {
                    "devkey": {
                        "acl": ["R", "W"],
                        "password": get_password_hash(username),
                    }
                },
                "password": get_password_hash(username),
                "uname": f"{username}",
            }
        )
        ds.user.save(username, user_data)

        if not TESTING:
            logger.info("%s:%s", username, username)

    ds.user.commit()
    ds.user_avatar.commit()


def generate_useful_dossier(users: list[User]) -> Dossier:
    "generate a useful dossier object"
    type = choice(["global", "personal"])

    dossier = Dossier(
        {
            "title": f"{get_random_word()} {get_random_word()}",
            "query": f'howler.analytic:"{choice(EXAMPLE_ANALYTICS)}"',
            "type": type,
            "owner": [choice(users).uname],
        }
    )

    for _ in range(randint(1, 3)):
        dossier.leads.append(
            Lead(
                {
                    "icon": choice(
                        ["material-symbols:cottage", "material-symbols:cardiology", "token-branded:rainbow"]
                    ),
                    "label": {"en": get_random_word(), "fr": get_random_word()},
                    "format": "markdown",
                    "content": f"# Hello, World!\n{get_random_word()} {get_random_word()} {get_random_word()}",
                    "metadata": {},
                }
            )
        )

    for i in range(randint(1, 3)):
        dossier.pivots.append(
            Pivot(
                {
                    "icon": choice(
                        ["material-symbols:cottage", "material-symbols:cardiology", "token-branded:rainbow"]
                    ),
                    "label": {"en": get_random_word(), "fr": get_random_word()},
                    "value": f"https://google.com/search?q={{{{test{i}}}}} and {{{{custom_value}}}}",
                    "format": "link",
                    "mappings": [
                        {"key": f"test{i}", "field": choice(list(Hit.flat_fields().keys()))},
                        {"key": "custom_value", "field": "custom", "custom_value": get_random_word()},
                    ],
                }
            )
        )

    return dossier


def generate_useful_case(ds: HowlerDatastore, generated_case_ids: list[str] = []):  # noqa: C901
    """Create a random, useful/cogent case for synthetic data.

    Generates a case with realistic structure including items (alerts, events, references,
    markdown notes), tasks, and correlation rules. Items are organized in a hierarchical
    structure with parent-child relationships.

    Args:
        ds: The Howler datastore instance to query users, hits, and events from.
        generated_case_ids: List of previously generated case IDs to link as related cases.

    Returns:
        A Case object populated with random but coherent data including items, tasks,
        and correlation rules.
    """
    users = ds.user.search("uname:*", rows=200, as_obj=True)["items"]
    hits = ds.hit.search("howler.id:*", rows=200, as_obj=True)["items"]
    events = ds.event.search("howler.id:*", rows=200, as_obj=True)["items"]
    existing_case_ids = [case.get("case_id") for case in ds.case.search("case_id:*", rows=200, as_obj=False)["items"]]

    case_titles = [
        "Suspicious Domain Investigation",
        "Credential Abuse Review",
        "Potential Lateral Movement",
        "Malware Activity Follow-up",
        "Phishing Campaign Triage",
        "Command-and-Control Infrastructure Review",
        "Account Takeover Investigation",
        "Data Exfiltration Assessment",
        "Endpoint Persistence Hunt",
        "Cloud Identity Abuse Case",
        "Ransomware Precursor Analysis",
        "Privileged Access Misuse Inquiry",
        "Suspicious Authentication Wave",
        "Infrastructure Reconnaissance Tracking",
        "Incident Correlation Workup",
        "Unusual Process Chain Investigation",
        "Network Beaconing Validation",
    ]
    case_summaries = [
        "Correlate alerts and events tied to suspicious infrastructure.",
        "Track and validate activity linked to potential credential misuse.",
        "Review telemetry associated with suspicious movement indicators.",
        "Aggregate related detections to determine likely attack progression.",
        "Evaluate whether suspicious events represent coordinated malicious activity.",
        "Document impacted entities and prioritize response and containment actions.",
        "Identify high-confidence indicators and map likely attacker objectives.",
        "Assess scope and confidence of signals before escalation decisions.",
        "Compare observed behaviors with known threat tradecraft patterns.",
        "Triangulate evidence from endpoint, network, and identity sources.",
        "Validate detections and eliminate benign explanations where possible.",
        "Build a concise evidence trail to support investigation handoff.",
        "Track suspicious artifacts and define follow-up hunting pivots.",
    ]
    target_pool = [
        "victim1",
        "victim2",
        "workstation-22",
        "server-01",
        "mail-gateway",
        "domain-controller-01",
        "vpn-gateway",
        "finance-laptop-07",
        "hr-workstation-03",
        "prod-k8s-node-2",
        "jump-host-1",
        "db-cluster-primary",
    ]
    threat_pool = [
        "evildomain.com",
        "badc2.example",
        "evilcomputer1",
        "198.51.100.42",
        "malicious-user",
        "stealth-update.net",
        "cdn-sync-check.com",
        "45.77.11.90",
        "dropbox-mirror.app",
        "backup-telemetry.co",
        "ntp-anomaly.host",
        "88.198.22.17",
    ]
    reference_name_pool = [
        "Initial Report",
        "Incident Timeline",
        "Executive Summary",
        "Technical Notes",
        "Containment Plan",
        "External Advisory",
        "Threat Brief",
        "Stakeholder Update",
        "Evidence Index",
        "Detection Review",
    ]
    markdown_template_pool = [
        (
            "# Analyst Notes\n\n"
            "## Hypothesis\n"
            "{hypothesis}\n\n"
            "## Observations\n"
            "- Target: `{target}`\n"
            "- Threat: `{threat}`\n"
            "- Confidence: {confidence}\n"
        ),
        (
            "# Investigation Update\n\n"
            "## Timeline\n"
            "1. Collected initial indicators.\n"
            "2. Validated event overlap.\n"
            "3. Prepared containment recommendation.\n\n"
            "## Current Focus\n"
            "{focus}\n"
        ),
        (
            "# Triage Checklist\n\n"
            "- [x] Validate alert context\n"
            "- [x] Correlate related events\n"
            "- [ ] Confirm blast radius\n"
            "- [ ] Draft handoff summary\n\n"
            "## Assigned Analyst\n"
            "{analyst}\n"
        ),
        (
            "# IOC Notes\n\n"
            "| Type | Value |\n"
            "| --- | --- |\n"
            "| Host | {target} |\n"
            "| Indicator | {threat} |\n\n"
            "## Next Action\n"
            "{next_action}\n"
        ),
    ]
    confidence_pool = ["Low", "Moderate", "High", "High (pending confirmation)"]
    focus_pool = [
        "Verify whether this activity is tied to an active intrusion set.",
        "Compare endpoint and identity telemetry for shared artifacts.",
        "Validate if suspicious authentication events match known attacker tradecraft.",
        "Identify additional systems that should be prioritized for containment.",
    ]
    next_action_pool = [
        "Pivot on destination infrastructure across the previous 14 days.",
        "Request endpoint triage package and memory capture for impacted host.",
        "Confirm privileged account exposure and reset credentials if required.",
        "Escalate to incident commander with correlated evidence bundle.",
    ]

    def _parse_timestamp(value: str | datetime | None) -> datetime | None:
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    case_id = get_random_id()

    selected_hits = sample(hits, k=min(len(hits), randint(5, 15))) if hits else []
    selected_events = sample(events, k=min(len(events), randint(3, 9))) if events else []

    selected_targets = sample(target_pool, k=randint(1, min(3, len(target_pool))))
    selected_threats = sample(threat_pool, k=randint(1, min(3, len(threat_pool))))
    selected_participants = [
        user.get("uname") for user in sample(users, k=min(len(users), randint(1, 3))) if user.get("uname")
    ]

    timeline_datetimes = [
        parsed
        for parsed in (_parse_timestamp(record.timestamp) for record in [*selected_hits, *selected_events])
        if parsed is not None
    ]

    case_start = min(timeline_datetimes).isoformat() if timeline_datetimes else None
    case_end = max(timeline_datetimes).isoformat() if timeline_datetimes else None
    case_created = case_start or datetime.now().isoformat()
    case_updated = choice(
        [
            None,
            datetime.now().isoformat(),
            case_end,
        ]
    )

    case = Case(
        {
            "case_id": case_id,
            "title": choice(case_titles),
            "escalation": choice(["normal", "focus", "crisis"]),
            "summary": choice(case_summaries),
            "overview": f"# {choice(case_titles)}\n\n{choice(case_summaries)}",
            "created": case_created,
            "updated": case_updated,
            "start": case_start,
            "end": case_end,
            "targets": selected_targets,
            "threats": selected_threats,
            "indicators": list(set(selected_targets + selected_threats))[:5],
            "participants": selected_participants,
            "enrichments": [],
        }
    )

    for hit in selected_hits:
        parent = case_service.get_parent_from_path(case, "alerts", create_if_missing=True)

        case.items.append(
            CaseItem(
                {
                    "name": f"{hit.howler.analytic} ({hit.howler.id})",
                    "parent": parent.id if parent else None,
                    "type": "hit",
                    "value": hit.howler.id,
                }
            )
        )

    for event in selected_events:
        parent = case_service.get_parent_from_path(case, "events", create_if_missing=True)

        case.items.append(
            CaseItem(
                {
                    "name": f"{get_random_word()} ({event.howler.id})",
                    "parent": parent.id if parent else None,
                    "type": "event",
                    "value": event.howler.id,
                }
            )
        )

    # Add a few additional deeply nested paths for existing hits/events
    nested_hit_candidates = sample(selected_hits, k=min(len(selected_hits), randint(1, 3))) if selected_hits else []
    for hit in nested_hit_candidates:
        parent = case_service.get_parent_from_path(
            case, f"alerts/{get_random_word()}/{get_random_word()}", create_if_missing=True
        )

        case.items.append(
            CaseItem(
                {
                    "name": f"{get_random_word()} ({hit.howler.id})",
                    "parent": parent.id if parent else None,
                    "type": "hit",
                    "value": hit.howler.id,
                }
            )
        )

    nested_event_candidates = (
        sample(
            selected_events,
            k=min(len(selected_events), randint(1, 2)),
        )
        if selected_events
        else []
    )
    for event in nested_event_candidates:
        parent = case_service.get_parent_from_path(
            case, f"alerts/{get_random_word()}/{get_random_word()}", create_if_missing=True
        )

        case.items.append(
            CaseItem(
                {
                    "name": f"{get_random_word()} ({event.howler.id})",
                    "parent": parent.id if parent else None,
                    "type": "event",
                    "value": event.howler.id,
                }
            )
        )

    available_related_case_ids = [
        cid for cid in [*existing_case_ids, *generated_case_ids] if isinstance(cid, str) and cid != case_id
    ]
    selected_related_case_ids = (
        sample(available_related_case_ids, k=min(len(available_related_case_ids), randint(0, 3)))
        if available_related_case_ids
        else []
    )

    for idx, related_case_id in enumerate(selected_related_case_ids, start=1):
        case.items.append(
            CaseItem(
                {
                    "name": f"Related Case {idx}",
                    "type": "case",
                    "value": related_case_id,
                }
            )
        )

    selected_reference_names = sample(reference_name_pool, k=randint(1, 3))
    for reference_name in selected_reference_names:
        parent = case_service.get_parent_from_path(case, "references", create_if_missing=True)
        case.items.append(
            CaseItem(
                {
                    "name": reference_name,
                    "type": "reference",
                    "value": "https://example.com",
                    "parent": parent.id if parent else None,
                }
            )
        )

    markdown_item_count = randint(2, 4)
    for index in range(markdown_item_count):
        markdown_parent = case_service.get_parent_from_path(
            case,
            choice(
                [
                    "analysis/notes",
                    "analysis/notes/daily",
                    "analysis/notes/triage",
                    f"analysis/{get_random_word()}",
                ]
            ),
            create_if_missing=True,
        )
        markdown_value = choice(markdown_template_pool).format(
            hypothesis=choice(
                [
                    "Potential credential theft followed by lateral movement.",
                    "Suspicious beaconing indicates possible command-and-control traffic.",
                    "Observed activity may represent staged data exfiltration.",
                    "Alerts suggest a coordinated phishing-to-access chain.",
                ]
            ),
            target=choice(selected_targets),
            threat=choice(selected_threats),
            confidence=choice(confidence_pool),
            focus=choice(focus_pool),
            analyst=choice(selected_participants or ["admin"]),
            next_action=choice(next_action_pool),
        )

        case.items.append(
            CaseItem(
                {
                    "name": f"Markdown Note {index + 1}",
                    "type": "markdown",
                    "value": markdown_value,
                    "parent": markdown_parent.id if markdown_parent else None,
                }
            )
        )

    task_count = randint(3, 7)
    for _ in range(task_count):
        case.tasks.append(
            CaseTask(
                {
                    "id": get_random_id(),
                    "complete": choice([True, False]),
                    "assignment": choice(selected_participants or ["admin"]),
                    "status": choice(Status.list()),
                    "summary": choice(
                        [
                            "Review related indicators and determine additional pivots.",
                            "Validate event context and identify correlations.",
                            "Confirm scope and impacted entities for this thread.",
                            "Assess whether this path supports active compromise.",
                            "Collect supporting evidence and update confidence level.",
                            "Compare this artifact against recent detection patterns.",
                            "Identify additional systems requiring triage for this lead.",
                            "Map this task output to containment or remediation actions.",
                            "Verify timeline consistency with known suspicious activity.",
                            "Check for related user and host activity across the same window.",
                            "Validate whether this indicator appears in prior incidents.",
                            "Document findings and propose next investigation pivots.",
                        ]
                    ),
                    "item": choice([item.id for item in case.items]) if case.items else None,
                }
            )
        )

    for _ in range(randint(1, 3)):
        timeframe = choice([7, 14, 28, None])

        case.rules.append(
            CaseRule(
                {
                    "destination": choice(
                        [
                            "alerts/{{howler.analytic}}",
                            "incoming/{{event.kind}}",
                            "alerts/{{howler.analytic}}/{{event.category}}",
                            "correlated/{{source.ip}}",
                            "triage/{{howler.escalation}}",
                        ]
                    ),
                    "query": choice(
                        [
                            f"destination.domain:{choice(threat_pool)}",
                            "source.ip:10.0.0.0/8 AND howler.analytic:Suspicious*",
                            "event.category:authentication AND event.outcome:failure",
                            "howler.escalation:focus OR howler.escalation:crisis",
                            f"destination.domain:{choice(threat_pool)} AND event.kind:alert",
                        ]
                    ),
                    "author": choice(selected_participants or ["admin"]),
                    "enabled": choice([True, True, True, False]),
                    "timeframe": timeframe,
                    "expire_after_resolved": choice([True, False]) if timeframe is not None else False,
                }
            )
        )

    return case
