from howler import odm
from howler.odm.models.ecs.egress import Egress
from howler.odm.models.ecs.ingress import Ingress
from howler.odm.models.ecs.interface import Interface


@odm.model(
    index=True,
    store=True,
    description=(
        "Observer is defined as a special network, security, or application device used to detect, observe, "
        "or create network, sercurity, or application event metrics"
    ),
)
class Observer(odm.Model):
    egress = odm.Optional(
        odm.Compound(
            Egress,
            description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
        )
    )
    hostname = odm.Optional(odm.Keyword(description="Hostname of the observer"))
    ingress = odm.Optional(
        odm.Compound(
            Ingress,
            description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
        )
    )
    interface = odm.Optional(
        odm.Compound(
            Interface,
            description="Interface being observed",
        )
    )
    ip = odm.List(odm.IP(description="IP addresses of the observer."), default=[])
    mac = odm.List(
        odm.Keyword(description="Mac addresses of the observer."),
        default=[],
    )
    name = odm.Optional(odm.Keyword(description="Custom name of the observer"))
    product = odm.Optional(odm.Keyword(description="Product name of the observer"))
    serial_number = odm.Optional(odm.Keyword(description="Observer serial number"))
    type = odm.Optional(odm.Keyword(description="Type of the observer the data is coming from"))
    vendor = odm.Optional(odm.Keyword(description="Vendor name of the observer"))
    version = odm.Optional(odm.Keyword(description="Observer version"))
