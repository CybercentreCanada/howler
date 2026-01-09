# mypy: ignore-errors
from typing import Literal

from howler import odm


@odm.model(index=True, store=True, description="Model of templates")
class Template(odm.Model):
    template_id: str = odm.UUID(description="A UUID for this template")
    analytic: str = odm.Keyword(description="The analytic which this template applies to.")
    detection: str | None = odm.Keyword(description="The detection which this template applies to.", optional=True)
    name: str | None = odm.Keyword(description="The name of the template.", optional=True, default=None)
    query: str | None = odm.Keyword(
        description="The query that controls when this template should be shown in the UI.", optional=True, default=None
    )
    type: Literal["personal"] | Literal["global"] = odm.Enum(
        values=["personal", "global"],
        description="The type of template - personal or global?",
    )
    owner: str | None = odm.Keyword(
        description="The person to whom this template belongs. Applies to personal templates only.",
        optional=True,
    )
    keys: list[str] = odm.List(
        odm.Keyword(),
        default=[],
        description="The list of fields to show when this template is used.",
    )
