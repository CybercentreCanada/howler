import json

from howler.odm.models.hit import Hit
from howler.odm.models.user import User


def make_user(name="analyst"):
    return User(
        {
            "uname": name,
            "name": name,
            "password": "not-a-real-password-hash",
            "type": ["user", "actionrunner_basic"],
            "classification": "U",
        }
    )


def make_hit(**howler):
    return Hit(
        {
            "classification": "U",
            "howler": {"analytic": "QA detection", "hash": "123abc", **howler},
            "event": {"original": "current telemetry"},
        }
    )


def make_lead(content="Analyst note", owner=None):
    return {
        "label": {"en": "AI Triage", "fr": "Triage IA"},
        "format": "markdown",
        "content": content,
        "metadata": json.dumps({"owner": owner}) if owner else None,
    }
