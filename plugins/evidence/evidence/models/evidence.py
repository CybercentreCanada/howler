"""Evidence Pydantic model: additional nested ECS objects attached to a Hit."""

from __future__ import annotations

from typing import Annotated

from howler.models import Date, EmptyableKeyword, HowlerEmbeddedModel, Keyword, mapping, metadata, register_model
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
    timestamp: Annotated[Date, metadata(default="NOW", reference=ECS_REFERENCE)]
    """Date/time when the event originated."""
    labels: mapping(Keyword, default={}, reference=ECS_REFERENCE)
    """Custom key/value pairs."""
    tags: Annotated[list[Keyword], metadata(reference=ECS_REFERENCE)] = []
    """List of keywords used to tag each event."""
    message: Annotated[EmptyableKeyword, metadata(reference=ECS_REFERENCE)] = ""
    """Log message for log events, optimized for viewing in a log viewer"""

    # Field Sets
    agent: Agent | None = None
    """Data about the software entity observing events."""
    cloud: Cloud | None = None
    """Fields related to the cloud or infrastructure."""
    container: Container | None = None
    """Container metadata."""
    destination: Client | None = None
    """Destination fields."""
    dns: DNS | None = None
    """Fields describing DNS queries and answers."""
    ecs: Annotated[ECSVersion, metadata(default={})]
    """Meta-information specific to ECS."""
    error: Error | None = None
    """These fields can represent errors of any kind."""
    event: ECSEvent | None = None
    """Context information about the log or metric event."""
    email: Email | None = None
    """Event details relating to an email transaction."""
    faas: FAAS | None = None
    """Function-as-a-service (FaaS) fields."""
    file: File | None = None
    """A file created on, or existing on, a filesystem."""
    group: Group | None = None
    """Groups relevant to the event."""
    host: Host | None = None
    """A general computing instance."""
    http: HTTP | None = None
    """Fields related to HTTP activity."""
    observer: Observer | None = None
    """A special network/security/application device."""
    interface: Interface | None = None
    """Ingress/egress interface information."""
    network: Network | None = None
    """Communication path over which an event happens."""
    organization: Organization | None = None
    """The company or entity data is associated with."""
    process: Process | None = None
    """Information about a process."""
    registry: Registry | None = None
    """Fields related to Windows Registry operations."""
    related: Related | None = None
    """Fields facilitating pivoting around a piece of data."""
    rule: Rule | None = None
    """Specifics of any observer or agent rules."""
    server: Server | None = None
    """The responder in a network connection."""
    source: Client | None = None
    """Source fields."""
    threat: Threat | None = None
    """Classification per a threat taxonomy."""
    tls: TLS | None = None
    """Fields related to a TLS connection."""
    url: URL | None = None
    """URL fields."""
    user: User | None = None
    """Information about the user relevant to the event."""
    user_agent: UserAgent | None = None
    """Fields normally from a browser request."""
    vulnerability: Vulnerability | None = None
    """Information about a vulnerability."""
