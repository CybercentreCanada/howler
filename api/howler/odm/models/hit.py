# mypy: ignore-errors
import importlib
from typing import Optional

from howler import odm
from howler.common.logging import get_logger
from howler.config import config
from howler.odm.models.assemblyline import AssemblyLine
from howler.odm.models.aws import AWS
from howler.odm.models.azure import Azure
from howler.odm.models.cbs import CBS
from howler.odm.models.ecs.agent import Agent
from howler.odm.models.ecs.client import Client
from howler.odm.models.ecs.cloud import Cloud
from howler.odm.models.ecs.container import Container
from howler.odm.models.ecs.dns import DNS
from howler.odm.models.ecs.email import Email
from howler.odm.models.ecs.error import Error
from howler.odm.models.ecs.event import Event
from howler.odm.models.ecs.faas import FAAS
from howler.odm.models.ecs.file import File
from howler.odm.models.ecs.group import Group
from howler.odm.models.ecs.host import Host
from howler.odm.models.ecs.http import HTTP
from howler.odm.models.ecs.interface import Interface
from howler.odm.models.ecs.network import Network
from howler.odm.models.ecs.observer import Observer
from howler.odm.models.ecs.organization import Organization
from howler.odm.models.ecs.process import Process
from howler.odm.models.ecs.registry import Registry
from howler.odm.models.ecs.related import Related
from howler.odm.models.ecs.rule import Rule
from howler.odm.models.ecs.server import Server
from howler.odm.models.ecs.threat import Threat
from howler.odm.models.ecs.tls import TLS
from howler.odm.models.ecs.url import URL
from howler.odm.models.ecs.user import User
from howler.odm.models.ecs.user_agent import UserAgent
from howler.odm.models.ecs.vulnerability import Vulnerability
from howler.odm.models.gcp import GCP
from howler.odm.models.howler_data import HowlerData

logger = get_logger(__file__)


@odm.model(index=True, store=True, description="ECS model version")
class ECSVersion(odm.Model):
    version: str = odm.Keyword(
        default="8.3.0",
        description="Additional information about the certificate status.",
    )


@odm.model(
    index=True,
    store=True,
    description="Howler Outline schema which is an extended version of Elastic Common Schema (ECS)",
)
class Hit(odm.Model):
    # Base Fields
    timestamp: str = odm.Date(
        default="NOW",
        description="Date/time when the event originated.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-base.html",
    )
    labels: dict[str, str] = odm.Mapping(
        odm.Keyword(),
        default={},
        description="Custom key/value pairs.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-base.html",
    )
    tags: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="List of keywords used to tag each event.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-base.html",
    )
    message: str = odm.Keyword(
        default="",
        description="Log message for log events, optimized for viewing in a log viewer",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-base.html",
    )

    # Howler extended fields. Deviates from ECS
    howler: HowlerData = odm.Compound(
        HowlerData,
        description="Howler specific definition of the hit that matches the outline.",
        reference="https://confluence.devtools.cse-cst.gc.ca/display/~jjgalar/Hit+Schema",
    )

    assemblyline: Optional[AssemblyLine] = odm.Optional(
        odm.Compound(
            AssemblyLine,
            description="AssemblyLine metadata associated with this alert.",
        )
    )

    # Field Sets
    agent: Agent = odm.Optional(
        odm.Compound(
            Agent,
            description="The agent fields contain the data about the software entity, "
            "if any, that collects, detects, or observes events on a host, or takes measurements on a host.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-agent.html",
        )
    )

    aws: AWS = odm.Optional(
        odm.Compound(
            AWS,
            description="Fields related to AWS.",
        )
    )

    azure: Azure = odm.Optional(
        odm.Compound(
            Azure,
            description="Fields related to Azure.",
        )
    )

    cbs: CBS = odm.Optional(odm.Compound(CBS, description="CBS metadata associated with this alert."))
    cloud: Cloud = odm.Optional(
        odm.Compound(
            Cloud,
            description="Fields related to the cloud or infrastructure the events are coming from.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-cloud.html",
        )
    )
    container: Container = odm.Optional(
        odm.Compound(
            Container,
            description="Container fields are used for meta information about the specific container "
            "that is the source of information.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-container.html",
        )
    )
    destination: Client = odm.Optional(
        odm.Compound(
            Client,
            description="Destination fields capture details about the receiver of a network exchange/packet.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-destination.html",
        )
    )
    dns: DNS = odm.Optional(
        odm.Compound(
            DNS,
            description="Fields describing DNS queries and answers.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-dns.html",
        )
    )
    ecs: ECSVersion = odm.Compound(
        ECSVersion,
        default={},
        description="Meta-information specific to ECS.",
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-ecs.html",
    )
    error: Error = odm.Optional(
        odm.Compound(
            Error,
            description="These fields can represent errors of any kind.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-error.html",
        )
    )
    event: Event = odm.Optional(
        odm.Compound(
            Event,
            description="The event fields are used for context information about the log or metric event itself.",
        )
    )
    email: Email = odm.Optional(
        odm.Compound(
            Email,
            description="Event details relating to an email transaction.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-event.html",
        )
    )
    faas: FAAS = odm.Optional(
        odm.Compound(
            FAAS,
            description="The user fields describe information about the function as a service "
            "(FaaS) that is relevant to the event.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-faas.html",
        )
    )
    file: File = odm.Optional(
        odm.Compound(
            File,
            description="A file is defined as a set of information that has been "
            "created on, or has existed on a filesystem.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-file.html",
        )
    )

    gcp: GCP = odm.Optional(
        odm.Compound(
            GCP,
            description="Fields related to Google Cloud Platform.",
        )
    )

    group: Group = odm.Optional(
        odm.Compound(
            Group,
            description="The group fields are meant to represent groups that are relevant to the event.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-group.html",
        )
    )
    host: Host = odm.Optional(
        odm.Compound(Host),
        description=(
            "A host is defined as a general computing instance. ECS host.* fields should be populated with details "
            "about the host on which the event happened, or from which the measurement was taken. Host types include "
            "hardware, virtual machines, Docker containers, and Kubernetes nodes."
        ),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-host.html",
    )
    http: HTTP = odm.Optional(
        odm.Compound(
            HTTP,
            description="Fields related to HTTP activity. Use the url field set to store the url of the request.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-http.html",
        )
    )
    observer: Observer = odm.Optional(
        odm.Compound(
            Observer,
            description=(
                "Observer is defined as a special network, security, or application device used to detect, obs"
                "erve, or create network, sercurity, or application event metrics"
            ),
        )
    )
    interface: Interface = odm.Optional(
        odm.Compound(
            Interface,
            description=(
                "The interface fields are used to record ingress and egress interface information when reported "
                "by an observer (e.g. firewall, router, load balancer) in the context of the observer handling a "
                "network connection. "
            ),
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-interface.html",
        )
    )
    network: Network = odm.Optional(
        odm.Compound(
            Network,
            description=(
                "The network is defined as the communication path over which a host or network event happens."
            ),
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-network.html",
        )
    )
    organization: Organization = odm.Optional(
        odm.Compound(
            Organization,
            description="The organization fields enrich data with information "
            "about the company or entity the data is associated with.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-organization.html",
        )
    )
    process: Process = odm.Optional(
        odm.Compound(
            Process,
            description="These fields contain information about a process.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-process.html",
        )
    )
    registry: Registry = odm.Optional(
        odm.Compound(
            Registry,
            description="Fields related to Windows Registry operations.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-registry.html",
        )
    )
    related: Related = odm.Optional(
        odm.Compound(
            Related,
            description="Fields related to Windows Registry operations.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-related.html",
        )
    )
    rule: Rule = odm.Optional(
        odm.Compound(
            Rule,
            description="Capture the specifics of any observer or agent rules",
        )
    )
    server: Server = odm.Optional(
        odm.Compound(Server),
        description=(
            "A Server is defined as the responder in a network connection for events regarding sessions, "
            "connections, or bidirectional flow records."
        ),
        reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-server.html",
    )
    source: Client = odm.Optional(
        odm.Compound(
            Client,
            description="Source fields capture details about the sender of a network exchange/packet.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-source.html",
        )
    )
    threat: Threat = odm.Optional(
        odm.Compound(
            Threat,
            description="Fields to classify events and alerts according to a threat taxonomy such as the "
            "MITRE ATT&CK® framework.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-threat.html",
        )
    )
    tls: TLS = odm.Optional(
        odm.Compound(
            TLS,
            description=(
                "Fields related to a TLS connection. These fields focus on the TLS protocol itself and "
                "intentionally avoids in-depth analysis of the related x.509 certificate files."
            ),
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-tls.html",
        )
    )
    url: URL = odm.Optional(
        odm.Compound(
            URL,
            description="URL fields provide support for complete or partial URLs, and "
            "supports the breaking down into scheme, domain, path, and so on.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-url.html",
        )
    )
    user: User = odm.Optional(
        odm.Compound(
            User,
            description="The user fields describe information about the user that is relevant to the event.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-user.html",
        )
    )
    user_agent: UserAgent = odm.Optional(
        odm.Compound(
            UserAgent,
            description="The user_agent fields normally come from a browser request.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-user_agent.html",
        )
    )
    vulnerability: Vulnerability = odm.Optional(
        odm.Compound(
            Vulnerability,
            description="The vulnerability fields describe information about a vulnerability that "
            "is relevant to an event.",
            reference="https://www.elastic.co/guide/en/ecs/8.5/ecs-vulnerability.html",
        )
    )


for plugin in config.core.plugins:
    try:
        importlib.import_module(f"{plugin}.odm.hit").modify_odm(Hit)
    except (ImportError, AttributeError):
        pass


if __name__ == "__main__":
    from pprint import pprint

    fields = {k: f"{v.__class__.__name__}{' (array)' if v.multivalued else ''}" for k, v in Hit.flat_fields().items()}
    pprint(fields)  # noqa: T203
