"""AssemblyLine metadata fields."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, list_field, optional, register_model

DEFAULT_MITRE: dict[str, list] = {"tactic": [], "technique": []}


@register_model(index=True, store=True, embedded=True)
class ALRecord(HowlerEmbeddedModel):
    """A single AssemblyLine detail record."""

    type: optional(keyword())
    subtype: optional(keyword())
    value: optional(keyword())
    verdict: optional(keyword())


@register_model(index=True, store=True, embedded=True)
class Mitre(HowlerEmbeddedModel):
    """MITRE ATT&CK tactic/technique records extracted by AssemblyLine."""

    tactic: list_field(compound(ALRecord), default=[])
    technique: list_field(compound(ALRecord), default=[])


@register_model(
    index=True,
    store=True,
    description="The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert.",
    embedded=True,
)
class AssemblyLine(HowlerEmbeddedModel):
    """The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert."""

    # al.detailed.av
    antivirus: list_field(compound(ALRecord), default=[])
    # al.detailed.attrib
    attribution: list_field(compound(ALRecord), default=[])
    # al.detailed.behavior
    behaviour: list_field(compound(ALRecord), default=[])
    # al.detailed.domain
    domain: list_field(compound(ALRecord), default=[])
    # al detailed.heuristic
    heuristic: list_field(compound(ALRecord), default=[])
    # al.detailed.[attack_category, attack_pattern]
    mitre: optional(compound(Mitre), default=DEFAULT_MITRE)
    # al.detailed.uri
    uri: list_field(compound(ALRecord), default=[])
    # al.detailed.yara
    yara: list_field(compound(ALRecord), default=[])
