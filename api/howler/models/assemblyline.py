"""AssemblyLine metadata fields."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from howler.models import HowlerEmbeddedModel, keyword, list_field, metadata, register_model

DEFAULT_MITRE: dict[str, list] = {"tactic": [], "technique": []}


@register_model(index=True, store=True, embedded=True)
class ALRecord(HowlerEmbeddedModel):
    """A single AssemblyLine detail record."""

    type: keyword(optional=True)
    subtype: keyword(optional=True)
    value: keyword(optional=True)
    verdict: keyword(optional=True)


@register_model(index=True, store=True, embedded=True)
class Mitre(HowlerEmbeddedModel):
    """MITRE ATT&CK tactic/technique records extracted by AssemblyLine."""

    tactic: list_field(ALRecord, default=[])
    technique: list_field(ALRecord, default=[])


@register_model(
    index=True,
    store=True,
    description="The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert.",
    embedded=True,
)
class AssemblyLine(HowlerEmbeddedModel):
    """The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert."""

    # al.detailed.av
    antivirus: list_field(ALRecord, default=[])
    # al.detailed.attrib
    attribution: list_field(ALRecord, default=[])
    # al.detailed.behavior
    behaviour: list_field(ALRecord, default=[])
    # al.detailed.domain
    domain: list_field(ALRecord, default=[])
    # al detailed.heuristic
    heuristic: list_field(ALRecord, default=[])
    # al.detailed.[attack_category, attack_pattern]
    mitre: Annotated[Mitre | None, metadata(optional=True), Field(default=DEFAULT_MITRE)]
    # al.detailed.uri
    uri: list_field(ALRecord, default=[])
    # al.detailed.yara
    yara: list_field(ALRecord, default=[])
