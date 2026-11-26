"""Base ECS record shared by Hit and Event top-level models."""

from __future__ import annotations

from typing import Annotated

from howler.config import CLASSIFICATION
from howler.models import (
    Classification,
    Date,
    EmptyableKeyword,
    HowlerEmbeddedModel,
    HowlerESModel,
    Keyword,
    mapping,
    metadata,
    register_model,
)
from howler.models.assemblyline import AssemblyLine
from howler.models.aws import AWS
from howler.models.azure import Azure
from howler.models.cbs import CBS
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
from howler.models.gcp import GCP

ECS_REFERENCE = "https://www.elastic.co/guide/en/ecs/8.5/ecs-base.html"


@register_model(index=True, store=True, description="ECS model version", embedded=True)
class ECSVersion(HowlerEmbeddedModel):
    """ECS model version."""

    version: Keyword = "8.3.0"
    """Additional information about the certificate status."""


class Record(HowlerESModel):
    """Base ECS fields shared by Hit and Event. Never registered/finalized directly."""

    _include_index = True

    # Base Fields
    timestamp: Annotated[Date, metadata(default="NOW", reference=ECS_REFERENCE)]
    """Date/time when the event originated."""
    classification: Annotated[Classification, metadata(copyto="__text__", default=CLASSIFICATION.UNRESTRICTED)]
    """Maximum classification for the hit"""
    labels: mapping(Keyword, default={}, reference=ECS_REFERENCE)
    """Custom key/value pairs."""
    tags: Annotated[list[Keyword], metadata(reference=ECS_REFERENCE)] = []
    """List of keywords used to tag each event."""
    message: Annotated[EmptyableKeyword, metadata(reference=ECS_REFERENCE)] = ""
    """Log message for log events, optimized for viewing in a log viewer"""

    assemblyline: AssemblyLine | None = None
    """AssemblyLine metadata associated with this alert."""

    # Field Sets
    agent: Annotated[Agent | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-agent.html")] = None
    (
        "The agent fields contain the data about the software entity, if any, that collects, detects, or observes "
        "events on a host, or takes measurements on a host."
    )
    aws: AWS | None = None
    """Fields related to AWS."""
    azure: Azure | None = None
    """Fields related to Azure."""
    cbs: CBS | None = None
    """CBS metadata associated with this alert."""
    cloud: Annotated[Cloud | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-cloud.html")] = None
    """Fields related to the cloud or infrastructure the events are coming from."""
    container: Annotated[
        Container | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-container.html")
    ] = None
    """Container fields are used for meta information about the specific container that is the source of information."""
    destination: Annotated[
        Client | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-destination.html")
    ] = None
    """Destination fields capture details about the receiver of a network exchange/packet."""
    dns: Annotated[DNS | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-dns.html")] = None
    """Fields describing DNS queries and answers."""
    ecs: Annotated[ECSVersion, metadata(reference=ECS_REFERENCE, default={})]
    """Meta-information specific to ECS."""
    error: Annotated[Error | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-error.html")] = None
    """These fields can represent errors of any kind."""
    event: ECSEvent | None = None
    """The event fields are used for context information about the log or metric event itself."""
    email: Annotated[Email | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-event.html")] = None
    """Event details relating to an email transaction."""
    faas: Annotated[FAAS | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-faas.html")] = None
    """The user fields describe information about the function as a service (FaaS) that is relevant to the event."""
    file: Annotated[File | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-file.html")] = None
    """A file is defined as a set of information that has been created on, or has existed on a filesystem."""
    gcp: GCP | None = None
    """Fields related to Google Cloud Platform."""
    group: Annotated[Group | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-group.html")] = None
    """The group fields are meant to represent groups that are relevant to the event."""
    host: Annotated[Host | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-host.html")] = None
    (
        "A host is defined as a general computing instance. ECS host.* fields should be populated with details about "
        "the host on which the event happened, or from which the measurement was taken. Host types include hardware, "
        "virtual machines, Docker containers, and Kubernetes nodes."
    )
    http: Annotated[HTTP | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-http.html")] = None
    """Fields related to HTTP activity. Use the url field set to store the url of the request."""
    observer: Observer | None = None
    (
        "Observer is defined as a special network, security, or application device used to detect, observe, or create "
        "network, sercurity, or application event metrics"
    )
    interface: Annotated[
        Interface | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-interface.html")
    ] = None
    (
        "The interface fields are used to record ingress and egress interface information when reported by an observer "
        "(e.g. firewall, router, load balancer) in the context of the observer handling a network connection. "
    )
    network: Annotated[
        Network | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-network.html")
    ] = None
    """The network is defined as the communication path over which a host or network event happens."""
    organization: Annotated[
        Organization | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-organization.html")
    ] = None
    """The organization fields enrich data with information about the company or entity the data is associated with."""
    process: Annotated[
        Process | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-process.html")
    ] = None
    """These fields contain information about a process."""
    registry: Annotated[
        Registry | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-registry.html")
    ] = None
    """Fields related to Windows Registry operations."""
    related: Annotated[
        Related | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-related.html")
    ] = None
    """Fields related to Windows Registry operations."""
    rule: Rule | None = None
    """Capture the specifics of any observer or agent rules"""
    server: Annotated[Server | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-server.html")] = (
        None
    )
    (
        "A Server is defined as the responder in a network connection for events regarding sessions, connections, or "
        "bidirectional flow records."
    )
    source: Annotated[Client | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-source.html")] = (
        None
    )
    """Source fields capture details about the sender of a network exchange/packet."""
    threat: Annotated[Threat | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-threat.html")] = (
        None
    )
    """Fields to classify events and alerts according to a threat taxonomy such as the MITRE ATT&CK® framework."""
    tls: Annotated[TLS | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-tls.html")] = None
    (
        "Fields related to a TLS connection. These fields focus on the TLS protocol itself and intentionally avoids "
        "in-depth analysis of the related x.509 certificate files."
    )
    url: Annotated[URL | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-url.html")] = None
    (
        "URL fields provide support for complete or partial URLs, and supports the breaking down into scheme, domain, "
        "path, and so on."
    )
    user: Annotated[User | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-user.html")] = None
    """The user fields describe information about the user that is relevant to the event."""
    user_agent: Annotated[
        UserAgent | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-user_agent.html")
    ] = None
    """The user_agent fields normally come from a browser request."""
    vulnerability: Annotated[
        Vulnerability | None, metadata(reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-vulnerability.html")
    ] = None
    """The vulnerability fields describe information about a vulnerability that is relevant to an event."""
