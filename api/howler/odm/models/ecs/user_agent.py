from howler import odm
from howler.odm.models.ecs.os import OS


@odm.model(index=True, store=True, description="Information about the device.")
class Device(odm.Model):
    name = odm.Optional(odm.Keyword(description="Name of the device."))


@odm.model(
    index=True,
    store=True,
    description="The user_agent fields normally come from a browser request.",
)
class UserAgent(odm.Model):
    device = odm.Optional(odm.Compound(Device, description="Information about the device."))
    name = odm.Optional(odm.Keyword(description="Name of the user agent."))
    original = odm.Optional(odm.Keyword(description="Unparsed user_agent string."))
    os = odm.Optional(odm.Compound(OS, description="OS fields contain information about the operating system."))
    version = odm.Optional(odm.Keyword(description="Version of the user agent."))
