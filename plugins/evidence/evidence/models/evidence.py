"""Evidence Pydantic model: additional nested ECS objects attached to a Hit."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    emptyable_keyword,
    keyword,
    list_field,
    mapping,
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
    agent: compound(Agent, optional=True, description="Data about the software entity observing events.")
    cloud: compound(Cloud, optional=True, description="Fields related to the cloud or infrastructure.")
    container: compound(Container, optional=True, description="Container metadata.")
    destination: compound(Client, optional=True, description="Destination fields.")
    dns: compound(DNS, optional=True, description="Fields describing DNS queries and answers.")
    ecs: compound(ECSVersion, default={}, description="Meta-information specific to ECS.")
    error: compound(Error, optional=True, description="These fields can represent errors of any kind.")
    event: compound(ECSEvent, optional=True, description="Context information about the log or metric event.")
    email: compound(Email, optional=True, description="Event details relating to an email transaction.")
    faas: compound(FAAS, optional=True, description="Function-as-a-service (FaaS) fields.")
    file: compound(File, optional=True, description="A file created on, or existing on, a filesystem.")
    group: compound(Group, optional=True, description="Groups relevant to the event.")
    host: compound(Host, optional=True, description="A general computing instance.")
    http: compound(HTTP, optional=True, description="Fields related to HTTP activity.")
    observer: compound(Observer, optional=True, description="A special network/security/application device.")
    interface: compound(Interface, optional=True, description="Ingress/egress interface information.")
    network: compound(Network, optional=True, description="Communication path over which an event happens.")
    organization: compound(Organization, optional=True, description="The company or entity data is associated with.")
    process: compound(Process, optional=True, description="Information about a process.")
    registry: compound(Registry, optional=True, description="Fields related to Windows Registry operations.")
    related: compound(Related, optional=True, description="Fields facilitating pivoting around a piece of data.")
    rule: compound(Rule, optional=True, description="Specifics of any observer or agent rules.")
    server: compound(Server, optional=True, description="The responder in a network connection.")
    source: compound(Client, optional=True, description="Source fields.")
    threat: compound(Threat, optional=True, description="Classification per a threat taxonomy.")
    tls: compound(TLS, optional=True, description="Fields related to a TLS connection.")
    url: compound(URL, optional=True, description="URL fields.")
    user: compound(User, optional=True, description="Information about the user relevant to the event.")
    user_agent: compound(UserAgent, optional=True, description="Fields normally from a browser request.")
    vulnerability: compound(Vulnerability, optional=True, description="Information about a vulnerability.")
