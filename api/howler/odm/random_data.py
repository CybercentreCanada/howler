import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from howler.odm.models.clue import Clue
from howler.plugins import get_plugins
from howler.utils.constants import TESTING

load_dotenv()

# We append the plugin directory for howler to the python part
PLUGIN_PATH = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))
sys.path.insert(0, str(PLUGIN_PATH))
sys.path.append(str(PLUGIN_PATH / f".venv/lib/python3.{sys.version_info.minor}/site-packages"))

import importlib
import json
import random
import textwrap
from datetime import datetime, timedelta
from random import choice, randint, sample
from typing import Any, Callable, cast
from uuid import uuid4

import yaml

from howler.common import loader
from howler.common.logging import get_logger
from howler.config import config
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.operations import OdmHelper
from howler.helper.hit import assess_hit
from howler.helper.oauth import VALID_CHARS
from howler.odm.base import Keyword
from howler.odm.helper import generate_useful_dossier, generate_useful_hit, generate_useful_observable
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic, Comment, Notebook, TriageOptions
from howler.odm.models.case import Case
from howler.odm.models.ecs.event import EVENT_CATEGORIES
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Assessment, Escalation, Scrutiny, Status
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.odm.randomizer import get_random_string, get_random_user, get_random_word, random_model_obj
from howler.security.utils import get_password_hash
from howler.services import analytic_service

classification = loader.get_classification()

logger = get_logger(__file__)

hit_helper = OdmHelper(Hit)


def run_modifications(odm: str, data: Any, log: bool = False):
    "Running modifications"
    new_keys: list[str] = []
    for plugin in get_plugins():  # pragma: no cover
        if generate := plugin.modules.odm.generation.get(odm, None):
            _new_keys, data = generate(data)
            new_keys += _new_keys

    if len(new_keys) > 0 and log:
        logger.debug("%s new top-level fields configured for %s", len(new_keys), odm)

    return data


def create_users(ds):
    """Create  number of user accounts"""
    admin_pass = os.getenv("DEV_ADMIN_PASS", "admin") or "admin"
    user_pass = os.getenv("DEV_USER_PASS", "user") or "user"
    shawnh_pass = "shawn-h"
    goose_pass = "goose"
    huey_pass = "huey"

    admin_hash = get_password_hash(admin_pass)

    admin_view = View(
        {
            "title": "view.assigned_to_me",
            "query": "howler.assignment:admin",
            "type": "readonly",
            "owner": "admin",
        }
    )

    admin_view = run_modifications("view", admin_view)

    user_data = User(
        {
            "apikeys": {
                "devkey": {"acl": ["R", "W", "E"], "password": admin_hash},
                "readonly": {"acl": ["R"], "password": admin_hash},
                "readonly1": {"acl": ["R"], "password": admin_hash},
                "impersonate": {"acl": ["R", "I"], "password": admin_hash},
                "readonly2": {"acl": ["R"], "password": admin_hash},
                "readonly3": {"acl": ["R"], "password": admin_hash},
                "write1": {"acl": ["W"], "password": admin_hash},
                "write2": {"acl": ["W"], "password": admin_hash},
                "both": {"acl": ["R", "W"], "password": admin_hash},
                "read_extended": {"acl": ["R", "E"], "password": admin_hash},
                "write_extended": {"acl": ["W", "E"], "password": admin_hash},
                "expired": {
                    "acl": ["R", "W", "E"],
                    "password": admin_hash,
                    "expiry_date": "2023-05-30T05:12:28.566Z",
                },
                "not_expired": {
                    "acl": ["R", "W", "E"],
                    "password": admin_hash,
                    "expiry_date": datetime.now().replace(year=3000).isoformat(),
                },
            },
            "classification": classification.RESTRICTED,
            "name": "Michael Scott",
            "email": "admin@howler.cyber.gc.ca",
            "password": admin_hash,
            "uname": "admin",
            "type": ["admin", "user", "automation_basic", "automation_advanced"],
            "groups": [
                "group1",
                "group2",
            ],
            "favourite_views": [admin_view.view_id],
        }
    )

    user_data = run_modifications("view", user_data, True)

    ds.user.save("admin", user_data)
    ds.user_avatar.save(
        "admin",
        "https://static.wikia.nocookie.net/theoffice/images/b/be/Character_-_MichaelScott.PNG",
    )
    ds.view.save(admin_view.view_id, admin_view)

    if not TESTING:
        logger.info("\t%s:%s", user_data.uname, admin_pass)

    user_hash = get_password_hash(user_pass)

    user_view = View(
        {
            "title": "view.assigned_to_me",
            "query": "howler.assignment:user",
            "type": "readonly",
            "owner": "user",
        }
    )

    user_data = User(
        {
            "name": "Dwight Schrute",
            "email": "user@howler.cyber.gc.ca",
            "apikeys": {
                "devkey": {"acl": ["R", "W"], "password": user_hash},
                "impersonate_admin": {
                    "acl": ["R", "W", "I"],
                    "agents": ["admin", "goose"],
                    "password": user_hash,
                },
                "impersonate_potato": {
                    "acl": ["R", "W", "I"],
                    "agents": ["potato"],
                    "password": user_hash,
                },
            },
            "password": user_hash,
            "uname": "user",
            "favourite_views": [user_view.view_id],
        }
    )

    user_view = run_modifications("view", user_view)
    user_data = run_modifications("user", user_data)

    ds.user.save("user", user_data)
    ds.user_avatar.save(
        "user",
        "https://static.wikia.nocookie.net/theoffice/images/c/c5/Dwight_.jpg",
    )
    ds.view.save(user_view.view_id, user_view)

    if not TESTING:
        logger.info("\t%s:%s", user_data.uname, user_pass)

    huey_hash = get_password_hash(huey_pass)

    huey_view = View(
        {
            "title": "view.assigned_to_me",
            "query": "howler.assignment:huey",
            "type": "readonly",
            "owner": "huey",
        }
    )

    huey_data = User(
        {
            "name": "Huey Guy",
            "email": "huey@howler.cyber.gc.ca",
            "apikeys": {
                "devkey": {"acl": ["R", "W"], "password": huey_hash},
                "impersonate_admin": {
                    "acl": ["R", "W", "I"],
                    "agents": ["admin", "goose"],
                    "password": huey_hash,
                },
                "impersonate_potato": {
                    "acl": ["R", "W", "I"],
                    "agents": ["potato"],
                    "password": huey_hash,
                },
            },
            "password": huey_hash,
            "uname": "huey",
            "favourite_views": [huey_view.view_id],
        }
    )

    huey_view = run_modifications("view", huey_view)
    huey_data = run_modifications("user", huey_data)

    ds.user.save("huey", huey_data)
    ds.user_avatar.save(
        "huey",
        "https://static.wikia.nocookie.net/theoffice/images/c/c5/Dwight_.jpg",
    )
    ds.view.save(huey_view.view_id, huey_view)

    if not TESTING:
        logger.info("\t%s:%s", huey_data.uname, huey_pass)

    shawnh_view = View(
        {
            "title": "view.assigned_to_me",
            "query": "howler.assignment:shawnh",
            "type": "readonly",
            "owner": "shawn-h",
        }
    )
    shawn_data = User(
        {
            "name": "Shawn Hannigans",
            "email": "shawn.hannigans@howler.com",
            "apikeys": {},
            "type": ["admin", "user"],
            "groups": ["group1", "group2"],
            "password": get_password_hash(shawnh_pass),
            "uname": "shawn-h",
            "favourite_views": [shawnh_view.view_id],
        }
    )

    shawnh_view = run_modifications("view", shawnh_view)
    shawn_data = run_modifications("user", shawn_data)

    ds.user.save("shawn-h", shawn_data)
    ds.view.save(shawnh_view.view_id, shawnh_view)

    if not TESTING:
        logger.info("\t%s:%s", shawn_data.uname, shawnh_pass)

    goose_view = View(
        {
            "title": "view.assigned_to_me",
            "query": "howler.assignment:goose",
            "type": "readonly",
            "owner": "goose",
        }
    )
    goose_data = User(
        {
            "name": "Mister Goose",
            "email": "goose@howler.cyber.gc.ca",
            "apikeys": {},
            "type": ["admin", "user"],
            "groups": ["group1", "group2"],
            "password": get_password_hash(goose_pass),
            "uname": "goose",
            "favourite_views": [goose_view.view_id],
        }
    )

    goose_view = run_modifications("view", goose_view)
    goose_data = run_modifications("user", goose_data)

    ds.user.save("goose", goose_data)
    ds.view.save(goose_view.view_id, goose_view)

    if not TESTING:
        logger.info("\t%s:%s", goose_data.uname, goose_pass)

    ds.user.commit()
    ds.user_avatar.commit()
    ds.view.commit()


def wipe_users(ds):
    """Wipe the users index"""
    ds.user.wipe()
    ds.user_avatar.wipe()
    ds.user.commit()
    ds.user_avatar.commit()


def create_templates(ds: HowlerDatastore):
    """Create some random templates"""
    for i in range(2):
        keys = sample(list(Hit.flat_fields().keys()), 5)

        for detection in ["Detection 1", "Detection 2"]:
            template = Template(
                {
                    "analytic": choice(["Password Checker", "Bad Guy Finder", "SecretAnalytic"]),
                    "detection": detection,
                    "type": "global",
                    "keys": keys,
                }
            )

            template = run_modifications("template", template, i == 0)

            ds.template.save(
                template.template_id,
                template,
            )

    for analytic in ["Password Checker", "Bad Guy Finder"]:
        template = Template(
            {
                "analytic": analytic,
                "type": "global",
                "keys": ["howler.id", "howler.hash"],
            }
        )

        template = run_modifications("template", template)

        ds.template.save(
            template.template_id,
            template,
        )

        template = Template(
            {
                "analytic": analytic,
                "owner": "admin",
                "type": "personal",
                "keys": ["howler.id", "howler.hash", "howler.analytic", "agent.id"],
            }
        )

        template = run_modifications("template", template)

        ds.template.save(
            template.template_id,
            template,
        )

        template = Template(
            {
                "analytic": analytic,
                "owner": "goose",
                "type": "personal",
                "keys": ["agent.id", "agent.type", "container.id"],
            }
        )

        ds.template.save(
            template.template_id,
            template,
        )

    ds.template.commit()


def wipe_templates(ds):
    """Wipe the templates index"""
    ds.template.wipe()


def create_overviews(ds: HowlerDatastore):
    """Create some random overviews"""
    for i in range(2):
        keys = sample(list(Hit.flat_fields().keys()), 5)

        for detection in ["Detection 1", "Detection 2"]:
            content = "\n\n".join(f"{{{key}}}" for key in keys)
            overview = Overview(
                {
                    "analytic": choice(["Password Checker", "Bad Guy Finder", "SecretAnalytic"]),
                    "owner": "admin",
                    "detection": detection,
                    "content": f"# Hello, World!\n\n{content}",
                }
            )

            overview = run_modifications("overview", overview, i == 0)

            ds.overview.save(
                overview.overview_id,
                overview,
            )

    for analytic in ["Password Checker", "Bad Guy Finder"]:
        overview = Overview(
            {
                "analytic": analytic,
                "owner": "admin",
                "content": textwrap.dedent("""
                    # {{howler.analytic}} Alert
                    {{#if (equals howler.status "open")}}
                    ![](https://img.shields.io/badge/open-blue)
                    {{/if}}
                    {{#if (equals howler.status "in-progress")}}
                    ![](https://img.shields.io/badge/in%20progress-yellow)
                    {{/if}}
                    {{#if (and (equals howler.status "resolved") (equals howler.escalation "miss"))}}
                    ![](https://img.shields.io/badge/safe-green)
                    {{/if}}
                    {{#if (and (equals howler.status "resolved") (equals howler.escalation "evidence"))}}
                    ![](https://img.shields.io/badge/malicious-red)
                    {{/if}}

                    `{{fetch "/api/v1/configs" "api_response.c12nDef.UNRESTRICTED"}}`

                    {{#if (and (equals howler.status "resolved") (equals howler.escalation "evidence"))}}
                    {{howler.rationale}}
                    {{/if}}

                    ## Summary

                    > {{howler.outline.summary}}

                    {{#if howler.assignment}}
                    <div style="display: grid; align-items: center; grid-template-columns: auto auto; width: fit-content; border: 1px solid grey; padding: 0.25rem; border-radius: 5px; margin-bottom: 1rem">
                    {{img src=(fetch (join "/api/v1/user/avatar/" howler.assignment ) "api_response") style="width: 32px; border-radius: 100px"}} {{howler.assignment}}
                    </div>
                    {{/if}}
                    """),  # noqa: E501
            }
        )

        overview = run_modifications("overview", overview)

        ds.overview.save(
            overview.overview_id,
            overview,
        )

    ds.overview.commit()


def wipe_overviews(ds):
    """Wipe the overviews index"""
    ds.overview.wipe()


def create_views(ds: HowlerDatastore):
    """Create some random views"""
    view = View(
        {
            "title": "CMT Hits",
            "query": "howler.analytic:cmt.*",
            "type": "global",
            "owner": "admin",
        }
    )

    view = run_modifications("view", view)

    ds.view.save(
        view.view_id,
        view,
    )

    fields = Hit.flat_fields()
    key_list = [key for key in fields.keys() if isinstance(fields[key], Keyword)]
    for _ in range(10):
        query = f"{choice(key_list)}:*{choice(VALID_CHARS)}* OR {choice(key_list)}:*{choice(VALID_CHARS)}*"
        view = View(
            {
                "title": get_random_word(),
                "query": query,
                "type": "global",
                "owner": get_random_user(),
            }
        )

        view = run_modifications("view", view)

        ds.view.save(
            view.view_id,
            view,
        )

    ds.view.commit()


def wipe_views(ds):
    """Wipe the views index"""
    ds.view.wipe()


def create_observables(ds: HowlerDatastore, observable_count: int = 200):
    """Create random observables in the datastore.

    Args:
        ds (HowlerDatastore): The datastore instance to save observables to.
        observable_count (int, optional): Number of observables to create. Defaults to 200.
    """
    lookups = loader.get_lookups()
    users = ds.user.search("*:*")["items"]
    for observable_index in range(observable_count):
        observable = generate_useful_observable(lookups, [user.uname for user in users], prune=False)
        ds.observable.save(observable.howler.id, observable)

        if observable_index % 25 == 0 and "pytest" not in sys.modules:
            logger.info("\tCreated %s/%s", observable_index, observable_count)

    logger.info(
        "%s total observables in datastore",
        ds.observable.search(query="howler.id:*", track_total_hits=True, rows=0)["total"],
    )


def create_hits(ds: HowlerDatastore, hit_count: int = 200):
    """Create some random records"""
    lookups = loader.get_lookups()
    users = ds.user.search("*:*")["items"]
    observable_ids = [
        obs["howler"]["id"] for obs in ds.observable.search("howler.id:*", rows=200, as_obj=False)["items"]
    ]
    created_hit_ids: list[str] = []
    for hit_idx in range(hit_count):
        hit = generate_useful_hit(
            lookups,
            [user.uname for user in users],
            prune_hit=False,
            hit_ids=created_hit_ids,
            observable_ids=observable_ids,
        )

        if hit_idx + 1 == hit_count:
            hit.howler.analytic = "SecretAnalytic"
            hit.howler.detection = None

        if config.core.clue.enabled:
            hit.clue = Clue(
                {
                    "types": [
                        {"field": "destination.user.group.id", "type": "domain"},
                        {"field": "dns.response_code", "type": "url"},
                        {"field": "file.name", "type": "url"},
                        {"field": "faas.name", "type": "domain"},
                    ]
                }
            )

        ds.hit.save(hit.howler.id, hit)
        created_hit_ids.append(hit.howler.id)
        analytic_service.save_from_hit(hit, random.choice(users))
        ds.analytic.commit()

        if choice([True, False, False, False]):
            user = choice(users)
            ds.hit.update(
                hit.howler.id,
                [
                    *assess_hit(
                        assessment=choice(Assessment.list()),
                        rationale=get_random_string(),
                        hit=hit,
                    ),
                    hit_helper.update(
                        "howler.assignment",
                        user.get("uname", user.get("username", None)),
                    ),
                    hit_helper.update("howler.status", Status.RESOLVED),
                ],
            )

        ds.hit.commit()

        if hit_idx % 25 == 0 and not TESTING:
            logger.info("\tCreated %s/%s", hit_idx, hit_count)

    if not TESTING:
        logger.info("\tCreated %s/%s", hit_idx + 1, hit_count)

    logger.info(
        "%s total hits in datastore", ds.hit.search(query="howler.id:*", track_total_hits=True, rows=0)["total"]
    )


def wipe_hits(ds):
    """Wipe the hits index"""
    ds.hit.wipe()


def wipe_observables(ds):
    """Wipe the observables index"""
    ds.observable.wipe()


def create_cases(ds: HowlerDatastore, num_cases: int = 5):
    """Create random cases using references to random alerts and observables."""
    users = ds.user.search("uname:*", rows=200, as_obj=False)["items"]
    hits = ds.hit.search("howler.id:*", rows=200, as_obj=False)["items"]
    observables = ds.observable.search("howler.id:*", rows=200, as_obj=False)["items"]
    existing_case_ids = [case.get("case_id") for case in ds.case.search("case_id:*", rows=200, as_obj=False)["items"]]
    generated_case_ids: list[str] = []

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
        "Correlate alerts and observables tied to suspicious infrastructure.",
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

    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    for _ in range(num_cases):
        case_id = f"case-{get_random_string(12).lower()}"

        selected_hits = sample(hits, k=min(len(hits), randint(5, 15))) if hits else []
        selected_observables = sample(observables, k=min(len(observables), randint(3, 9))) if observables else []

        items: list[dict[str, str]] = []

        for idx, hit in enumerate(selected_hits, start=1):
            hit_id = hit.get("howler", {}).get("id")
            if not hit_id:
                continue

            items.append(
                {
                    "path": f"alerts/{hit['howler']['analytic']} ({hit['howler']['id']})",
                    "type": "hit",
                    "value": hit_id,
                }
            )

        for idx, observable in enumerate(selected_observables, start=1):
            observable_id = observable.get("howler", {}).get("id")
            if not observable_id:
                continue

            items.append(
                {
                    "path": f"observable/{observable['howler']['id']}",
                    "type": "observable",
                    "value": observable_id,
                }
            )

        # Add a few additional deeply nested paths for existing hits/observables
        nested_hit_candidates = sample(selected_hits, k=min(len(selected_hits), randint(1, 3))) if selected_hits else []
        for nested_hit in nested_hit_candidates:
            nested_hit_id = nested_hit.get("howler", {}).get("id")
            if not nested_hit_id:
                continue

            items.append(
                {
                    "path": f"alerts/{get_random_word()}/{get_random_word()}",
                    "type": "hit",
                    "value": nested_hit_id,
                }
            )

        nested_observable_candidates = (
            sample(
                selected_observables,
                k=min(len(selected_observables), randint(1, 2)),
            )
            if selected_observables
            else []
        )
        for nested_observable in nested_observable_candidates:
            nested_observable_id = nested_observable.get("howler", {}).get("id")
            if not nested_observable_id:
                continue

            items.append(
                {
                    "path": f"alerts/{get_random_word()}/{get_random_word()}/{get_random_word()}",
                    "type": "observable",
                    "value": nested_observable_id,
                }
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
            items.append(
                {
                    "path": f"cases/Related Case {idx}",
                    "type": "case",
                    "value": related_case_id,
                }
            )

        selected_reference_names = sample(reference_name_pool, k=randint(1, 3))
        for idx, reference_name in enumerate(selected_reference_names, start=1):
            items.append({"path": f"references/{reference_name}", "type": "reference", "value": "https://example.com"})

        selected_targets = sample(target_pool, k=randint(1, min(3, len(target_pool))))
        selected_threats = sample(threat_pool, k=randint(1, min(3, len(threat_pool))))
        selected_participants = [
            user.get("uname") for user in sample(users, k=min(len(users), randint(1, 3))) if user.get("uname")
        ]

        timeline_datetimes = [
            parsed
            for parsed in (
                _parse_timestamp(record.get("timestamp")) for record in [*selected_hits, *selected_observables]
            )
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

        task_count = randint(3, 7)
        tasks = []
        for _ in range(task_count):
            tasks.append(
                {
                    "id": str(uuid4()),
                    "complete": choice([True, False]),
                    "assignment": choice(selected_participants or ["admin"]),
                    "status": choice(Status.list()),
                    "summary": choice(
                        [
                            "Review related indicators and determine additional pivots.",
                            "Validate observable context and identify correlations.",
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
                    "path": choice([item["path"] for item in items]) if items else "alerts/alert1",
                }
            )

        case_data = Case(
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
                "items": items,
                "enrichments": [],
                "rules": [
                    {
                        "id": str(uuid4()),
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
                        "timeframe": choice(
                            [
                                (datetime.now() + timedelta(days=randint(7, 28))).isoformat(),
                                (datetime.now() + timedelta(days=randint(7, 28))).isoformat(),
                                None,
                            ]
                        ),
                    }
                    for _ in range(randint(1, 3))
                ],
                "tasks": tasks,
            }
        )

        case_data = run_modifications("case", case_data)

        ds.case.save(case_id, case_data)
        generated_case_ids.append(case_id)

        case_hit_ids = list({item["value"] for item in items if item.get("type") == "hit"})
        case_observable_ids = list({item["value"] for item in items if item.get("type") == "observable"})

        for hit_id in case_hit_ids:
            ds.hit.update(hit_id, [hit_helper.list_add("howler.related", case_id)])

        for observable_id in case_observable_ids:
            ds.observable.update(observable_id, [hit_helper.list_add("howler.related", case_id)])

    ds.case.commit()


def wipe_cases(ds):
    """Wipe the cases index"""
    ds.case.wipe()


def random_escalations() -> list[Escalation]:
    """Return a list of random escalations"""
    return random.sample(Escalation.list(), k=random.randint(1, len(Escalation.list())))


def random_scrutinies() -> list[Scrutiny]:
    """Return a list of random scrutinies"""
    return random.sample(Scrutiny.list(), k=random.randint(1, len(Scrutiny.list())))


def random_event_categories():
    """Return a list of random event categories"""
    return random.choice(EVENT_CATEGORIES)


def create_analytics(ds: HowlerDatastore, num_analytics: int = 10):
    """Create some random analytics"""
    users = [user.uname for user in ds.user.search("*:*")["items"]]

    for analytic in ds.analytic.search("*:*")["items"]:
        for detection in analytic.detections:
            analytic.comment.append(
                Comment(
                    {
                        "value": f"Placeholder Comment - {detection}",
                        "user": random.choice(users),
                        "detection": detection,
                    }
                )
            )

        analytic.comment.append(
            Comment(
                {
                    "value": "Placeholder Comment - Analytic",
                    "user": random.choice(users),
                }
            )
        )

        if config.core.notebook.enabled:
            analytic.notebooks.append(
                Notebook(
                    {
                        "value": "Link to super notebook",
                        "name": "Super notebook",
                        "user": random.choice(users),
                    }
                )
            )

        analytic = run_modifications("analytic", analytic)

        ds.analytic.save(analytic.analytic_id, analytic)

    fields = Hit.flat_fields()
    key_list = [key for key in fields.keys() if isinstance(fields[key], Keyword)]
    for _ in range(num_analytics):
        a: Analytic = random_model_obj(cast(Any, Analytic))
        a.name = " ".join([get_random_word().capitalize() for _ in range(random.randint(1, 3))])
        a.detections = list(set(a.detections))
        a.owner = random.choice(users)
        a.contributors = list(set(random.sample(users, k=random.randint(1, 3))))
        a.rule = None
        a.rule_crontab = None
        a.rule_type = None

        assessments = Assessment.list()

        cast(TriageOptions, a.triage_settings).valid_assessments = list(
            set(random.sample(assessments, counts=([3] * len(assessments)), k=random.randint(1, len(assessments) * 3)))
        )

        a = run_modifications("analytic", a)

        ds.analytic.save(a.analytic_id, a)

    for rule_type in ["lucene", "eql", "sigma"]:
        a: Analytic = random_model_obj(cast(Any, Analytic))
        a.rule_type = rule_type
        a.name = " ".join([get_random_word().capitalize() for _ in range(random.randint(1, 3))])
        a.detections = ["Rule"]
        a.owner = random.choice(users)
        a.contributors = list(set(random.sample(users, k=random.randint(1, 3))))
        a.rule_crontab = (
            f"{','.join([str(k) for k in sorted(random.sample(list(range(60)), k=random.randint(2, 5)))])} * * * *"
        )

        cast(TriageOptions, a.triage_settings).valid_assessments = list(
            set(random.sample(assessments, counts=([3] * len(assessments)), k=random.randint(1, len(assessments) * 3)))
        )

        if a.rule_type == "lucene":
            a.rule = (
                f"{choice(key_list)}:*{choice(VALID_CHARS)}*\n#example "
                f"comment\nOR\n{choice(key_list)}:*{choice(VALID_CHARS)}*"
            )
        elif a.rule_type == "eql":
            category1 = random_event_categories()
            category2 = random_event_categories()

            a.rule = textwrap.dedent(
                f"""
            sequence
                [ {category1} where howler.escalation in ({", ".join([f'"{item}"' for item in random_escalations()])}) ]
                [ {category2} where howler.scrutiny in ({", ".join([f'"{item}"' for item in random_scrutinies()])}) ]
            """
            ).strip()
        elif a.rule_type == "sigma":
            files = []

            sigma_dir = Path(__file__).parent / "sigma"
            if sigma_dir.exists():
                files = list(sigma_dir.glob("*.yml"))

            if len(files) > 0:
                file_name = random.choice(files)
                file_data = file_name.read_text("utf-8")
                data = yaml.safe_load(file_data)
                a.name = data["title"]
                a.description = data["description"]
                a.rule = file_data
            else:
                logger.warning(
                    "For better test data using sigma rules, execute howler/external/generate_sigma_rules.py."
                )

        a = run_modifications("analytic", a)

        ds.analytic.save(a.analytic_id, a)

    ds.analytic.commit()
    ds.hit.commit()


def wipe_analytics(ds):
    """Wipe the analytics index"""
    ds.analytic.wipe()


def create_actions(ds: HowlerDatastore, num_actions: int = 30):
    """Create random actions"""
    fields = Hit.flat_fields()
    key_list = [key for key in fields.keys() if isinstance(fields[key], Keyword)]
    users = ds.user.search("*:*")["items"]

    module_path = Path(__file__).parents[1] / "actions"
    available_operations = {
        operation.OPERATION_ID: operation
        for operation in (
            importlib.import_module(f"howler.actions.{module.stem}")
            for module in module_path.iterdir()
            if module.suffix == ".py" and module.name != "__init__.py"
        )
    }

    operation_options = list(available_operations.keys())
    if "transition" in operation_options:
        operation_options.remove("transition")

    for _ in range(num_actions):
        operations: list[dict[str, str]] = []
        operation_ids = sample(operation_options, k=randint(1, len(operation_options)))
        for operation_id in operation_ids:
            action_data = {}

            for step in available_operations[operation_id].specification()["steps"]:
                for key in step["args"].keys():
                    potential_values = step.get("options", {}).get(key, None)
                    if potential_values:
                        if isinstance(potential_values, dict):
                            try:
                                action_data[key] = choice(potential_values[choice(list(potential_values.keys()))])
                            except IndexError:
                                continue
                        else:
                            action_data[key] = choice(potential_values)
                    else:
                        action_data[key] = get_random_word()

            if operation_id == "prioritization":
                action_data["value"] = float(random.randint(0, 10000)) / 10

            operations.append({"operation_id": operation_id, "data_json": json.dumps((action_data))})

        action = Action(
            {
                "name": get_random_word(),
                "owner_id": choice([user["uname"] for user in users]),
                "query": f"{choice(key_list)}:*{choice(VALID_CHARS)}* OR {choice(key_list)}:*{choice(VALID_CHARS)}*",
                "operations": operations,
            }
        )

        action = run_modifications("action", action)

        ds.action.save(action.action_id, action)

    ds.action.commit()


def wipe_actions(ds: HowlerDatastore):
    """Wipe the actions index"""
    ds.action.wipe()


def create_dossiers(ds: HowlerDatastore, num_dossiers: int = 5):
    "Create random dossiers"
    users = ds.user.search("*:*")["items"]
    for _ in range(num_dossiers):
        dossier = generate_useful_dossier(users)
        ds.dossier.save(dossier.dossier_id, dossier)

    ds.dossier.commit()


def wipe_dossiers(ds: HowlerDatastore):
    """Wipe the dossiers index"""
    ds.dossier.wipe()


def setup_hits(ds):
    "Set up hits index"
    os.environ["ELASTIC_HIT_SHARDS"] = "1"
    os.environ["ELASTIC_HIT_REPLICAS"] = "1"
    ds.hit.fix_shards()
    ds.hit.fix_replicas()


def setup_observables(ds):
    "Set up hits index"
    os.environ["ELASTIC_HIT_SHARDS"] = "1"
    os.environ["ELASTIC_HIT_REPLICAS"] = "1"
    ds.observable.fix_shards()
    ds.observable.fix_replicas()


def setup_users(ds):
    "Set up users index"
    os.environ["ELASTIC_USER_REPLICAS"] = "1"
    os.environ["ELASTIC_USER_AVATAR_REPLICAS"] = "1"
    ds.user.fix_replicas()
    ds.user_avatar.fix_replicas()


INDEXES: dict[str, tuple[Callable, list[Callable]]] = {
    "users": (wipe_users, [create_users]),
    "templates": (wipe_templates, [create_templates]),
    "overviews": (wipe_overviews, [create_overviews]),
    "views": (wipe_views, [create_views]),
    "observables": (wipe_observables, [create_observables]),
    "hits": (wipe_hits, [create_hits]),
    "cases": (wipe_cases, [create_cases]),
    "analytics": (wipe_analytics, [create_analytics]),
    "actions": (wipe_actions, [create_actions]),
    "dossiers": (wipe_dossiers, [create_dossiers]),
}

if __name__ == "__main__":
    # TODO: Implement a solid command line interface for running this

    args = [*sys.argv]

    # Remove the file path
    args.pop(0)

    if "all" in args or len(args) < 1:
        logger.info("Adding test data to all indexes.")
        args = list(INDEXES.keys())
    else:
        logger.info("Adding test data to indexes: (%s).", ", ".join(args))

    ds = loader.datastore(archive_access=False)

    if "--no-wipe" not in args:
        logger.info("Wiping existing data.")

        for index, operations in INDEXES.items():
            if index in args:
                # Wipe function
                operations[0](ds)

    logger.info("Running setup steps.")
    if "hits" in args:
        setup_hits(ds)

    if "observables" in args:
        setup_observables(ds)

    if "users" in args:
        setup_users(ds)

    for index, operations in INDEXES.items():
        if index in args:
            logger.info("Creating %s...", index)

            # Create functions
            for create_fn in operations[1]:
                create_fn(ds)

    logger.info("Done.")
