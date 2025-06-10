# mypy: ignore-errors
from typing import Optional

from howler import odm
from howler.plugins import get_plugins


@odm.model(index=True, store=True, description="Model of overviews")
class Overview(odm.Model):
    overview_id: str = odm.UUID(description="A UUID for this overview")
    analytic: str = odm.Keyword(description="The analytic which this overview applies to.")
    detection: Optional[str] = odm.Keyword(description="The detection which this overview applies to.", optional=True)
    owner: Optional[str] = odm.Keyword(
        description="The person to whom this overview belongs.",
        optional=True,
    )
    content: str = odm.Keyword(description="The markdown to show when this overview is used.")


for plugin in get_plugins():
    if modify_odm := plugin.modules.odm.modify_odm.get("overview"):
        modify_odm(Overview)
