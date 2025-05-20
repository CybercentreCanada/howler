from howler import odm


@odm.model(
    index=True,
    store=True,
)
class ALRecord(odm.Model):
    type: str = odm.Optional(odm.Keyword())
    subtype: str = odm.Optional(odm.Keyword())
    value: str = odm.Optional(odm.Keyword())
    verdict: str = odm.Optional(odm.Keyword())


@odm.model(
    index=True,
    store=True,
)
class Mitre(odm.Model):
    tactic: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    technique: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])


DEFAULT_MITRE: dict[str, list[ALRecord]] = {"tactic": [], "technique": []}


@odm.model(
    index=True,
    store=True,
    description="The AssemblyLine fields contain any data obtained from AssemblyLine relating to the alert.",
)
class AssemblyLine(odm.Model):
    # al.detailed.av
    antivirus: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    # al.detailed.attrib
    attribution: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    # al.detailed.behavior
    behaviour: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    # al.detailed.domain
    domain: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    # al detailed.heuristic
    heuristic: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    # al.detailed.[attack_category, attack_pattern]
    mitre: Mitre = odm.Optional(odm.Compound(Mitre), default=DEFAULT_MITRE)
    # al.detailed.uri
    uri: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
    # al.detailed.yara
    yara: list[ALRecord] = odm.List(odm.Compound(ALRecord), default=[])
