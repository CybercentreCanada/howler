import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# We append the plugin directory for howler to the python part
PLUGIN_PATH = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))
sys.path.insert(0, str(PLUGIN_PATH))
sys.path.append(str(PLUGIN_PATH / f".venv/lib/python3.{sys.version_info.minor}/site-packages"))

import importlib
import json
import random
import textwrap
from datetime import datetime
from random import choice, randint, sample
from typing import Any, Callable, cast

import yaml

from howler.common import loader
from howler.common.logging import get_logger
from howler.config import config
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.operations import OdmHelper
from howler.helper.hit import assess_hit
from howler.helper.oauth import VALID_CHARS
from howler.odm.base import Keyword
from howler.odm.helper import generate_useful_dossier, generate_useful_hit
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic, Comment, Notebook, TriageOptions
from howler.odm.models.ecs.event import EVENT_CATEGORIES
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Assessment, Escalation, HitStatus, Scrutiny
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
    ds.user.save("admin", user_data)
    ds.user_avatar.save(
        "admin",
        "https://static.wikia.nocookie.net/theoffice/images/b/be/Character_-_MichaelScott.PNG",
    )
    ds.view.save(admin_view.view_id, admin_view)

    if "pytest" not in sys.modules:
        logger.info(f"\t{user_data.uname}:{admin_pass}")

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
    ds.user.save("user", user_data)
    ds.user_avatar.save(
        "user",
        "https://static.wikia.nocookie.net/theoffice/images/c/c5/Dwight_.jpg",
    )
    ds.view.save(user_view.view_id, user_view)

    if "pytest" not in sys.modules:
        logger.info(f"\t{user_data.uname}:{user_pass}")

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
    ds.user.save("huey", huey_data)
    ds.user_avatar.save(
        "huey",
        "https://static.wikia.nocookie.net/theoffice/images/c/c5/Dwight_.jpg",
    )
    ds.view.save(huey_view.view_id, huey_view)

    if "pytest" not in sys.modules:
        logger.info(f"\t{huey_data.uname}:{huey_pass}")

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

    shawn_data.favourite_views.append(shawnh_view.view_id)
    ds.user.save("shawn-h", shawn_data)
    ds.view.save(shawnh_view.view_id, shawnh_view)

    if "pytest" not in sys.modules:
        logger.info(f"\t{shawn_data.uname}:{shawnh_pass}")

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

    goose_data.favourite_views.append(goose_view.view_id)
    ds.user.save("goose", goose_data)
    ds.view.save(goose_view.view_id, goose_view)

    if "pytest" not in sys.modules:
        logger.info(f"\t{goose_data.uname}:{goose_pass}")

    ds.user.commit()
    ds.user_avatar.commit()
    ds.view.commit()


def wipe_users(ds):
    """Wipe the users index"""
    ds.user.wipe()
    ds.user_avatar.wipe()


def create_templates(ds: HowlerDatastore):
    """Create some random templates"""
    for _ in range(2):
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
    for _ in range(2):
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

    ds.view.save(
        view.view_id,
        view,
    )

    view = View(
        {
            "title": "Howler Bundles",
            "query": "howler.is_bundle:true",
            "type": "readonly",
            "owner": "none",
        }
    )

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

        ds.view.save(
            view.view_id,
            view,
        )

    ds.view.commit()


def wipe_views(ds):
    """Wipe the views index"""
    ds.view.wipe()


def create_hits(ds: HowlerDatastore, hit_count: int = 200):
    """Create some random hits"""
    lookups = loader.get_lookups()
    users = ds.user.search("*:*")["items"]
    for hit_idx in range(hit_count):
        hit = generate_useful_hit(lookups, [user["uname"] for user in users], prune_hit=False)

        if hit_idx + 1 == hit_count:
            hit.howler.analytic = "SecretAnalytic"
            hit.howler.detection = None

        ds.hit.save(hit.howler.id, hit)
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
                    hit_helper.update("howler.status", HitStatus.RESOLVED),
                ],
            )

        ds.hit.commit()

        if hit_idx % 25 == 0 and "pytest" not in sys.modules:
            logger.info("\tCreated %s/%s", hit_idx, hit_count)

    if "pytest" not in sys.modules:
        logger.info("\tCreated %s/%s", hit_idx + 1, hit_count)

    logger.info(
        "%s total hits in datastore", ds.hit.search(query="howler.id:*", track_total_hits=True, rows=0)["total"]
    )


def create_bundles(ds: HowlerDatastore):
    """Create some random bundles"""
    lookups = loader.get_lookups()
    users = [user.uname for user in ds.user.search("*:*")["items"]]

    hits = {}

    for i in range(3):
        bundle_hit: Hit = generate_useful_hit(lookups, users)
        bundle_hit.howler.is_bundle = True

        for hit in ds.hit.search("howler.is_bundle:false", rows=randint(3, 10), offset=(i * 2))["items"]:
            if hit.howler.id not in hits:
                hits[hit.howler.id] = hit

            bundle_hit.howler.hits.append(hit.howler.id)
            hits[hit.howler.id].howler.bundles.append(bundle_hit.howler.id)

        analytic_service.save_from_hit(bundle_hit, random.choice(ds.user.search("*:*")["items"]))
        bundle_hit.howler.bundle_size = len(bundle_hit.howler.hits)
        ds.hit.save(bundle_hit.howler.id, bundle_hit)

    for hit in hits.values():
        ds.hit.save(hit.howler.id, hit)

    ds.hit.commit()


def wipe_hits(ds):
    """Wipe the hits index"""
    ds.hit.wipe()


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
                    potential_values = step["options"].get(key, None)
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
    os.environ["ELASTIC_HIT_SHARDS"] = "12"
    os.environ["ELASTIC_HIT_REPLICAS"] = "1"
    ds.hit.fix_shards()
    ds.hit.fix_replicas()


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
    "hits": (wipe_hits, [create_hits, create_bundles]),
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

    if "users" in args:
        setup_users(ds)

    for index, operations in INDEXES.items():
        if index in args:
            logger.info(f"Creating {index}...")

            # Create functions
            for create_fn in operations[1]:
                create_fn(ds)

    logger.info("Done.")
