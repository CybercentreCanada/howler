# mypy: ignore-errors
from typing import Literal, Optional, Union

from howler import odm


@odm.model(index=True, store=True, description="Model of templates")
class Template(odm.Model):
    template_id: str = odm.UUID(description="A UUID for this template")
    analytic: str = odm.Keyword(description="The analytic which this template applies to.")
    detection: Optional[str] = odm.Keyword(description="The detection which this template applies to.", optional=True)
    type: Union[Literal["personal"], Literal["global"]] = odm.Enum(
        values=["personal", "global"],
        description="The type of template - personal or global?",
    )
    owner: Optional[str] = odm.Keyword(
        description="The person to whom this template belongs. Applies to personal templates only.",
        optional=True,
    )
    keys: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="The list of fields to show when this template is used.",
    )
