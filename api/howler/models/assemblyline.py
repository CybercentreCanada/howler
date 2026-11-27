"""AssemblyLine metadata fields."""

from __future__ import annotations

from typing import Annotated

from howler.models import HowlerEmbeddedModel, Keyword, metadata, register_model

DEFAULT_MITRE: dict[str, list] = {"tactic": [], "technique": []}


@register_model(index=True, store=True, embedded=True)
class ALRecord(HowlerEmbeddedModel):
    """A single AssemblyLine detail record."""

    type: Keyword | None = None
    subtype: Keyword | None = None
    value: Keyword | None = None
    verdict: Keyword | None = None


@register_model(index=True, store=True, embedded=True)
class Mitre(HowlerEmbeddedModel):
    """MITRE ATT&CK tactic/technique records extracted by AssemblyLine."""

    tactic: list[ALRecord] = []
    technique: list[ALRecord] = []


@register_model(
    index=True,
    store=True,
    description="The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert.",
    embedded=True,
)
class AssemblyLine(HowlerEmbeddedModel):
    """The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert."""

    # al.detailed.av
    antivirus: list[ALRecord] = []
    # al.detailed.attrib
    attribution: list[ALRecord] = []
    # al.detailed.behavior
    behaviour: list[ALRecord] = []
    # al.detailed.domain
    domain: list[ALRecord] = []
    # al detailed.heuristic
    heuristic: list[ALRecord] = []
    # al.detailed.[attack_category, attack_pattern]
    mitre: Annotated[Mitre | None, metadata(optional=True, default=DEFAULT_MITRE)]
    # al.detailed.uri
    uri: list[ALRecord] = []
    # al.detailed.yara
    yara: list[ALRecord] = []
