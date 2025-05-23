from typing import Literal, Optional, Union

from howler import odm
from howler.odm.models.lead import Lead
from howler.odm.models.pivot import Pivot


@odm.model(
    index=True,
    store=True,
    description="The dossier object stores individual tabs/fields for a given alert.",
)
class Dossier(odm.Model):
    dossier_id: str = odm.UUID(description="A UUID for this dossier.")
    leads: list[Lead] = odm.List(
        odm.Compound(Lead),
        default=[],
        description="A list of the leads to show when the query matches the given alert.",
    )
    pivots: list[Pivot] = odm.List(
        odm.Compound(Pivot),
        default=[],
        description="A list of the pivots to show when the query matches the given alert.",
    )
    title: str = odm.Keyword(description="The title of this dossier.")
    owner: str = odm.Keyword(description="The person to whom this dossier belongs.")
    query: Optional[str] = odm.Keyword(
        description="The query that controls when this dossier should be shown in the UI.", optional=True, default=None
    )
    type: Union[Literal["personal"], Literal["global"]] = odm.Enum(
        values=["personal", "global"],
        description="The type of dossier - personal or global.",
    )
