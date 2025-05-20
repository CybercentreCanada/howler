from howler import odm
from howler.odm.models.ecs.interface import Interface


@odm.model(
    index=True,
    store=True,
    description="Holds information like interface number, name, vlan, and zone to classify ingress traffic",
)
class Ingress(odm.Model):
    zone = odm.Optional(odm.Keyword(description="Network zone of incoming traffic as reported by observer"))
    interface = odm.Optional(odm.Compound(Interface, description="Ingress Interface"))
