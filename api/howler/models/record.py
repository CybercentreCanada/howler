"""Base ECS record shared by Hit and Event top-level models."""

from __future__ import annotations

from howler.config import CLASSIFICATION
from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    classification,
    compound,
    date,
    emptyable_keyword,
    keyword,
    list_field,
    mapping,
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

    version: keyword(default="8.3.0", description="Additional information about the certificate status.")


class Record(HowlerESModel):
    """Base ECS fields shared by Hit and Event. Never registered/finalized directly."""

    _include_index = True

    # Base Fields
    timestamp: date(default="NOW", description="Date/time when the event originated.", reference=ECS_REFERENCE)
    classification: classification(
        is_user_classification=False,
        copyto="__text__",
        default=CLASSIFICATION.UNRESTRICTED,
        description="Maximum classification for the hit",
    )
    labels: mapping(keyword(), default={}, description="Custom key/value pairs.", reference=ECS_REFERENCE)
    tags: list_field(
        keyword(), default=[], description="List of keywords used to tag each event.", reference=ECS_REFERENCE
    )
    message: emptyable_keyword(
        default="",
        description="Log message for log events, optimized for viewing in a log viewer",
        reference=ECS_REFERENCE,
    )

    assemblyline: compound(AssemblyLine, optional=True, description="AssemblyLine metadata associated with this alert.")

    # Field Sets
    agent: compound(
        Agent,
        optional=True,
        description="The agent fields contain the data about the software entity, "
        "if any, that collects, detects, or observes events on a host, or takes measurements on a host.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-agent.html",
    )
    aws: compound(AWS, optional=True, description="Fields related to AWS.")
    azure: compound(Azure, optional=True, description="Fields related to Azure.")
    cbs: compound(CBS, optional=True, description="CBS metadata associated with this alert.")
    cloud: compound(
        Cloud,
        optional=True,
        description="Fields related to the cloud or infrastructure the events are coming from.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-cloud.html",
    )
    container: compound(
        Container,
        optional=True,
        description="Container fields are used for meta information about the specific container "
        "that is the source of information.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-container.html",
    )
    destination: compound(
        Client,
        optional=True,
        description="Destination fields capture details about the receiver of a network exchange/packet.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-destination.html",
    )
    dns: compound(
        DNS,
        optional=True,
        description="Fields describing DNS queries and answers.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-dns.html",
    )
    ecs: compound(ECSVersion, default={}, description="Meta-information specific to ECS.", reference=ECS_REFERENCE)
    error: compound(
        Error,
        optional=True,
        description="These fields can represent errors of any kind.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-error.html",
    )
    event: compound(
        ECSEvent,
        optional=True,
        description="The event fields are used for context information about the log or metric event itself.",
    )
    email: compound(
        Email,
        optional=True,
        description="Event details relating to an email transaction.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-event.html",
    )
    faas: compound(
        FAAS,
        optional=True,
        description="The user fields describe information about the function as a service "
        "(FaaS) that is relevant to the event.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-faas.html",
    )
    file: compound(
        File,
        optional=True,
        description="A file is defined as a set of information that has been "
        "created on, or has existed on a filesystem.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-file.html",
    )
    gcp: compound(GCP, optional=True, description="Fields related to Google Cloud Platform.")
    group: compound(
        Group,
        optional=True,
        description="The group fields are meant to represent groups that are relevant to the event.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-group.html",
    )
    host: compound(
        Host,
        optional=True,
        description=(
            "A host is defined as a general computing instance. ECS host.* fields should be populated with details "
            "about the host on which the event happened, or from which the measurement was taken. Host types "
            "include hardware, virtual machines, Docker containers, and Kubernetes nodes."
        ),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-host.html",
    )
    http: compound(
        HTTP,
        optional=True,
        description="Fields related to HTTP activity. Use the url field set to store the url of the request.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-http.html",
    )
    observer: compound(
        Observer,
        optional=True,
        description=(
            "Observer is defined as a special network, security, or application device used to detect, obs"
            "erve, or create network, sercurity, or application event metrics"
        ),
    )
    interface: compound(
        Interface,
        optional=True,
        description=(
            "The interface fields are used to record ingress and egress interface information when reported "
            "by an observer (e.g. firewall, router, load balancer) in the context of the observer handling a "
            "network connection. "
        ),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-interface.html",
    )
    network: compound(
        Network,
        optional=True,
        description=("The network is defined as the communication path over which a host or network event happens."),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-network.html",
    )
    organization: compound(
        Organization,
        optional=True,
        description="The organization fields enrich data with information "
        "about the company or entity the data is associated with.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-organization.html",
    )
    process: compound(
        Process,
        optional=True,
        description="These fields contain information about a process.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-process.html",
    )
    registry: compound(
        Registry,
        optional=True,
        description="Fields related to Windows Registry operations.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-registry.html",
    )
    related: compound(
        Related,
        optional=True,
        description="Fields related to Windows Registry operations.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-related.html",
    )
    rule: compound(Rule, optional=True, description="Capture the specifics of any observer or agent rules")
    server: compound(
        Server,
        optional=True,
        description=(
            "A Server is defined as the responder in a network connection for events regarding sessions, "
            "connections, or bidirectional flow records."
        ),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-server.html",
    )
    source: compound(
        Client,
        optional=True,
        description="Source fields capture details about the sender of a network exchange/packet.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-source.html",
    )
    threat: compound(
        Threat,
        optional=True,
        description="Fields to classify events and alerts according to a threat taxonomy such as the "
        "MITRE ATT&CK® framework.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-threat.html",
    )
    tls: compound(
        TLS,
        optional=True,
        description=(
            "Fields related to a TLS connection. These fields focus on the TLS protocol itself and "
            "intentionally avoids in-depth analysis of the related x.509 certificate files."
        ),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-tls.html",
    )
    url: compound(
        URL,
        optional=True,
        description="URL fields provide support for complete or partial URLs, and "
        "supports the breaking down into scheme, domain, path, and so on.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-url.html",
    )
    user: compound(
        User,
        optional=True,
        description="The user fields describe information about the user that is relevant to the event.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-user.html",
    )
    user_agent: compound(
        UserAgent,
        optional=True,
        description="The user_agent fields normally come from a browser request.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-user_agent.html",
    )
    vulnerability: compound(
        Vulnerability,
        optional=True,
        description="The vulnerability fields describe information about a vulnerability that is relevant to an event.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-vulnerability.html",
    )
