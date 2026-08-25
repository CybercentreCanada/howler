"""Comprehensive flat-field parity differential test.

For every migrated model group, compares the canonical dotted field-path registry
(``model_registry.flat_fields``) against the legacy ODM's ``flat_fields()``. This is the
broadest differential signal available: it catches missing/renamed/extra fields across the
entire migrated schema (shared enums/primitives, all ECS field sets, Record/Hit/Event/Case,
and the remaining action/analytic/provider/dossier/overview/template/user/view models) without
requiring one bespoke test per field.
"""

from __future__ import annotations

import importlib

import pytest

from howler.models import model_registry

# (legacy module, new module, [class names]) triples covering every migrated model group.
MODEL_GROUPS: list[tuple[str, str, list[str]]] = [
    # Shared/base
    ("howler.odm.models.assemblyline", "howler.models.assemblyline", ["ALRecord", "Mitre", "AssemblyLine"]),
    ("howler.odm.models.aws", "howler.models.aws", ["Account", "Organization", "AWS"]),
    ("howler.odm.models.azure", "howler.models.azure", ["Azure"]),
    ("howler.odm.models.gcp", "howler.models.gcp", ["GCP"]),
    ("howler.odm.models.cbs", "howler.models.cbs", ["SharepointUser", "SharepointData", "Sharepoint", "CBS"]),
    ("howler.odm.models.localized_label", "howler.models.localized_label", ["LocalizedLabel"]),
    ("howler.odm.models.lead", "howler.models.lead", ["Lead"]),
    ("howler.odm.models.pivot", "howler.models.pivot", ["Mapping", "Pivot"]),
    ("howler.odm.models.clue", "howler.models.clue", ["TypeMap", "Clue"]),
    # ECS field sets
    ("howler.odm.models.ecs.agent", "howler.models.ecs.agent", ["Agent"]),
    ("howler.odm.models.ecs.autonomous_system", "howler.models.ecs.autonomous_system", ["AS"]),
    ("howler.odm.models.ecs.client", "howler.models.ecs.client", ["Nat", "OriginalClient", "Client"]),
    (
        "howler.odm.models.ecs.cloud",
        "howler.models.ecs.cloud",
        ["Account", "Instance", "Project", "Machine", "Service", "Cloud"],
    ),
    ("howler.odm.models.ecs.code_signature", "howler.models.ecs.code_signature", ["CodeSignature"]),
    ("howler.odm.models.ecs.container", "howler.models.ecs.container", ["Hash", "Image", "Container"]),
    ("howler.odm.models.ecs.dns", "howler.models.ecs.dns", ["DNSAnswer", "DNSQuestion", "DNS"]),
    ("howler.odm.models.ecs.egress", "howler.models.ecs.egress", ["Egress"]),
    ("howler.odm.models.ecs.elf", "howler.models.ecs.elf", ["Segment", "Section", "Header", "ELF"]),
    (
        "howler.odm.models.ecs.email",
        "howler.models.ecs.email",
        ["Address", "File", "Attachment", "ParentEmail", "Email"],
    ),
    ("howler.odm.models.ecs.error", "howler.models.ecs.error", ["Error"]),
    ("howler.odm.models.ecs.event", "howler.models.ecs.event", ["ECSEvent"]),
    ("howler.odm.models.ecs.faas", "howler.models.ecs.faas", ["Trigger", "FAAS"]),
    ("howler.odm.models.ecs.file", "howler.models.ecs.file", ["File"]),
    ("howler.odm.models.ecs.geo", "howler.models.ecs.geo", ["GeoPoint", "Geo"]),
    ("howler.odm.models.ecs.group", "howler.models.ecs.group", ["Group", "ShortGroup"]),
    ("howler.odm.models.ecs.hash", "howler.models.ecs.hash", ["Hashes"]),
    ("howler.odm.models.ecs.host", "howler.models.ecs.host", ["Host"]),
    ("howler.odm.models.ecs.http", "howler.models.ecs.http", ["Body", "Request", "Response", "HTTP"]),
    ("howler.odm.models.ecs.ingress", "howler.models.ecs.ingress", ["Ingress"]),
    ("howler.odm.models.ecs.interface", "howler.models.ecs.interface", ["Interface"]),
    ("howler.odm.models.ecs.network", "howler.models.ecs.network", ["Network"]),
    ("howler.odm.models.ecs.observer", "howler.models.ecs.observer", ["Observer"]),
    ("howler.odm.models.ecs.organization", "howler.models.ecs.organization", ["Organization"]),
    ("howler.odm.models.ecs.os", "howler.models.ecs.os", ["OS"]),
    ("howler.odm.models.ecs.pe", "howler.models.ecs.pe", ["PE"]),
    (
        "howler.odm.models.ecs.process",
        "howler.models.ecs.process",
        ["CharDevice", "TTY", "Thread", "EntryMeta", "ParentParentProcess", "ParentProcess", "Process"],
    ),
    ("howler.odm.models.ecs.registry", "howler.models.ecs.registry", ["RegistryData", "Registry"]),
    ("howler.odm.models.ecs.related", "howler.models.ecs.related", ["Related"]),
    ("howler.odm.models.ecs.rule", "howler.models.ecs.rule", ["Rule"]),
    ("howler.odm.models.ecs.server", "howler.models.ecs.server", ["Server"]),
    (
        "howler.odm.models.ecs.threat",
        "howler.models.ecs.threat",
        [
            "Email",
            "SubTechnique",
            "Technique",
            "Tactic",
            "Software",
            "Group",
            "Feed",
            "Indicator",
            "Matched",
            "Enrichments",
            "Threat",
        ],
    ),
    ("howler.odm.models.ecs.tls", "howler.models.ecs.tls", ["Server", "Client", "TLS"]),
    ("howler.odm.models.ecs.url", "howler.models.ecs.url", ["URL"]),
    ("howler.odm.models.ecs.user", "howler.models.ecs.user", ["UserNested", "User", "ShortUser"]),
    ("howler.odm.models.ecs.user_agent", "howler.models.ecs.user_agent", ["Device", "UserAgent"]),
    ("howler.odm.models.ecs.vulnerability", "howler.models.ecs.vulnerability", ["Vulnerability"]),
    # Top-level documents and their embedded data
    ("howler.odm.models.hit", "howler.models.hit", ["Hit"]),
    ("howler.odm.models.event", "howler.models.event", ["Event", "EventData", "Comment", "Log"]),
    ("howler.odm.models.howler_data", "howler.models.howler_data", ["HowlerData", "Link", "Comment", "Log", "Header"]),
    (
        "howler.odm.models.case",
        "howler.models.case",
        ["Case", "CaseItem", "CaseRule", "CaseTask", "CaseEnrichment", "CaseLog"],
    ),
    ("howler.odm.models.action", "howler.models.action", ["Action", "Operation"]),
    ("howler.odm.models.analytic", "howler.models.analytic", ["Analytic", "Comment", "TriageOptions", "Notebook"]),
    ("howler.odm.models.overview", "howler.models.overview", ["Overview"]),
    ("howler.odm.models.template", "howler.models.template", ["Template"]),
    ("howler.odm.models.user", "howler.models.user", ["User", "ApiKey", "DashboardEntry"]),
    ("howler.odm.models.view", "howler.models.view", ["View", "GridColumn", "Settings"]),
    ("howler.odm.models.dossier", "howler.models.dossier", ["Dossier"]),
]


def _flattened_cases() -> list[tuple[str, str, str]]:
    cases = []
    for legacy_module, new_module, names in MODEL_GROUPS:
        for name in names:
            cases.append((legacy_module, new_module, name))
    return cases


@pytest.mark.parametrize(
    "legacy_module,new_module,name",
    _flattened_cases(),
    ids=[f"{new_module.rsplit('.', 1)[-1]}.{name}" for legacy_module, new_module, name in _flattened_cases()],
)
def test_flat_field_parity(legacy_module: str, new_module: str, name: str) -> None:
    """Every migrated model's dotted field paths exactly match the legacy ODM's.

    ``Hit`` is special-cased: other session-scoped tests/fixtures (e.g. the
    ``HowlerDatastore`` fixture in ``test/conftest.py``) call the legacy
    ``Hit.add_namespace("clue", ...)`` without a matching ``remove_namespace`` in every path,
    which can permanently mutate the shared legacy ``Hit`` class for the rest of the test
    session depending on run order. The new model intentionally excludes Clue from the base
    ``Hit`` schema (it is an opt-in extension applied through ``howler.models.extensions``),
    so ``clue.*`` paths are excluded from this comparison rather than asserting on legacy
    global mutable state outside this module's control.
    """
    legacy_cls = getattr(importlib.import_module(legacy_module), name)
    new_cls = getattr(importlib.import_module(new_module), name)

    legacy_fields = {
        field for field in legacy_cls.flat_fields().keys() if not (name == "Hit" and field.startswith("clue"))
    }
    new_fields = set(model_registry.flat_fields(new_cls).keys())

    assert new_fields == legacy_fields
