"""Evidence Pydantic model: additional nested ECS objects attached to a Hit.

This mirrors ``evidence.odm.models.evidence.Evidence`` field-for-field, but is built on the
new ``howler.models`` Pydantic/DSL foundation instead of the legacy ODM. The legacy ``odm``
module keeps running unchanged until the Step 8 consumer/runtime cutover.
"""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    emptyable_keyword,
    keyword,
    list_field,
    mapping,
    optional,
    register_model,
)
from howler.models.ecs.agent import Agent
from howler.models.ecs.client import Client
from howler.models.ecs.cloud import Cloud
from howler.models.ecs.container import Container
from howler.models.ecs.dns import DNS
from howler.models.ecs.email import Email
from howler.models.ecs.error import Error
from howler.models.ecs.event import ECSEvent
from howler.models.ecs.faas import FAAS
from howler.models.ecs.file import File
from howler.models.ecs.group import Group
from howler.models.ecs.host import Host
from howler.models.ecs.http import HTTP
from howler.models.ecs.interface import Interface
from howler.models.ecs.network import Network
from howler.models.ecs.observer import Observer
from howler.models.ecs.organization import Organization
from howler.models.ecs.process import Process
from howler.models.ecs.registry import Registry
from howler.models.ecs.related import Related
from howler.models.ecs.rule import Rule
from howler.models.ecs.server import Server
from howler.models.ecs.threat import Threat
from howler.models.ecs.tls import TLS
from howler.models.ecs.url import URL
from howler.models.ecs.user import User
from howler.models.ecs.user_agent import UserAgent
from howler.models.ecs.vulnerability import Vulnerability
from howler.models.record import ECS_REFERENCE, ECSVersion


@register_model(index=True, store=True, description="Evidence fields add a list of additional ECS objects.")
class Evidence(HowlerEmbeddedModel):
    """Evidence fields add a list of additional ECS objects."""

    # Base Fields
    timestamp: date(default="NOW", description="Date/time when the event originated.", reference=ECS_REFERENCE)
    labels: mapping(keyword(), default={}, description="Custom key/value pairs.", reference=ECS_REFERENCE)
    tags: list_field(
        keyword(), default=[], description="List of keywords used to tag each event.", reference=ECS_REFERENCE
    )
    message: emptyable_keyword(
        default="",
        description="Log message for log events, optimized for viewing in a log viewer",
        reference=ECS_REFERENCE,
    )

    # Field Sets
    agent: optional(compound(Agent), description="Data about the software entity observing events.")
    cloud: optional(compound(Cloud), description="Fields related to the cloud or infrastructure.")
    container: optional(compound(Container), description="Container metadata.")
    destination: optional(compound(Client), description="Destination fields.")
    dns: optional(compound(DNS), description="Fields describing DNS queries and answers.")
    ecs: compound(ECSVersion, default={}, description="Meta-information specific to ECS.")
    error: optional(compound(Error), description="These fields can represent errors of any kind.")
    event: optional(compound(ECSEvent), description="Context information about the log or metric event.")
    email: optional(compound(Email), description="Event details relating to an email transaction.")
    faas: optional(compound(FAAS), description="Function-as-a-service (FaaS) fields.")
    file: optional(compound(File), description="A file created on, or existing on, a filesystem.")
    group: optional(compound(Group), description="Groups relevant to the event.")
    host: optional(compound(Host), description="A general computing instance.")
    http: optional(compound(HTTP), description="Fields related to HTTP activity.")
    observer: optional(compound(Observer), description="A special network/security/application device.")
    interface: optional(compound(Interface), description="Ingress/egress interface information.")
    network: optional(compound(Network), description="Communication path over which an event happens.")
    organization: optional(compound(Organization), description="The company or entity data is associated with.")
    process: optional(compound(Process), description="Information about a process.")
    registry: optional(compound(Registry), description="Fields related to Windows Registry operations.")
    related: optional(compound(Related), description="Fields facilitating pivoting around a piece of data.")
    rule: optional(compound(Rule), description="Specifics of any observer or agent rules.")
    server: optional(compound(Server), description="The responder in a network connection.")
    source: optional(compound(Client), description="Source fields.")
    threat: optional(compound(Threat), description="Classification per a threat taxonomy.")
    tls: optional(compound(TLS), description="Fields related to a TLS connection.")
    url: optional(compound(URL), description="URL fields.")
    user: optional(compound(User), description="Information about the user relevant to the event.")
    user_agent: optional(compound(UserAgent), description="Fields normally from a browser request.")
    vulnerability: optional(compound(Vulnerability), description="Information about a vulnerability.")
