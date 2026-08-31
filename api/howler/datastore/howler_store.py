from typing import TYPE_CHECKING, Any

from howler.common.exceptions import HowlerAttributeError
from howler.config import config
from howler.datastore.collection import ESCollection, logger
from howler.models import model_extensions
from howler.models import schema as new_schema
from howler.models.action import Action as SchemaAction
from howler.models.analytic import Analytic as SchemaAnalytic
from howler.models.case import Case as SchemaCase
from howler.models.clue import declare_hit_extension as declare_clue_hit_extension
from howler.models.dossier import Dossier as SchemaDossier
from howler.models.event import Event as SchemaEvent
from howler.models.hit import Hit as SchemaHit
from howler.models.overview import Overview as SchemaOverview
from howler.models.template import Template as SchemaTemplate
from howler.models.user import User as SchemaUser
from howler.models.view import View as SchemaView
from howler.odm.base import Compound
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic
from howler.odm.models.case import Case
from howler.odm.models.clue import Clue
from howler.odm.models.config import ILMIndexConfig
from howler.odm.models.dossier import Dossier
from howler.odm.models.event import Event
from howler.odm.models.hit import Hit
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.plugins import get_plugins

if TYPE_CHECKING:
    from howler.datastore.store import ESStore

INDEX_MODELS = {
    "hit": (Hit, SchemaHit),
    "event": (Event, SchemaEvent),
    "case": (Case, SchemaCase),
    "template": (Template, SchemaTemplate),
    "overview": (Overview, SchemaOverview),
    "analytic": (Analytic, SchemaAnalytic),
    "action": (Action, SchemaAction),
    "user": (User, SchemaUser),
    "view": (View, SchemaView),
    "dossier": (Dossier, SchemaDossier),
    "user_avatar": (None, None),
}

# Keep the legacy table exported for differential tooling and the Step 8 consumer rewrite.
# Registered collections use finalized Pydantic/DSL models for persistence starting in Step 7.
INDEXES = {name: models[0] for name, models in INDEX_MODELS.items()}
SCHEMA_INDEXES = {name: models[1] for name, models in INDEX_MODELS.items()}

ILM_ENABLED_INDEXES = {"hit", "event", "case"}


class HowlerDatastore(object):
    def __init__(self, datastore_object: "ESStore"):
        self.ds: "ESStore" = datastore_object

        # Reset/compose new-model plugin extension state deterministically on every datastore
        # startup. ``model_extensions`` is a process-wide singleton; without this reset, a prior
        # ``HowlerDatastore``/test instance's declared or finalized extensions (e.g. Clue applied
        # in one test but not another) would silently leak into this one, purely depending on
        # import/construction order.
        model_extensions.clear()

        plugins = get_plugins()
        for plugin in plugins:
            legacy_only_targets = {
                target
                for target in plugin.modules.odm.modify_odm
                if SCHEMA_INDEXES.get(target) is not None and target not in plugin.modules.models.declare_extensions
            }
            if legacy_only_targets:
                targets = ", ".join(sorted(legacy_only_targets))
                raise HowlerAttributeError(
                    f"Plugin {plugin.name} defines legacy ODM extensions for {targets} without matching typed "
                    "model extensions. Add modules.models.declare_extensions entries before using this plugin "
                    "with Pydantic-backed collections."
                )

        for plugin in plugins:
            for _index, _odm in INDEXES.items():
                if _odm is None:
                    continue

                if modify_odm := plugin.modules.odm.modify_odm.get(_index):
                    logger.info("Modifying %s odm with function from plugin %s", _index, plugin.name)
                    modify_odm(_odm)

        if config.core.clue.enabled:
            Hit.add_namespace(
                "clue",
                Compound(Clue, description="Clue-specific overrides for this alert", default=None, optional=True),
            )
            declare_clue_hit_extension()

        for plugin in plugins:
            for _index in SCHEMA_INDEXES:
                if declare_extension := plugin.modules.models.declare_extensions.get(_index):
                    logger.info("Declaring %s model extension with function from plugin %s", _index, plugin.name)
                    declare_extension()

        finalized_schema_models: dict[str, Any] = {}
        for _index, _schema in SCHEMA_INDEXES.items():
            if _schema is None:
                finalized_schema_models[_index] = None
                continue

            finalized = model_extensions.finalize(_schema)
            # Validate every finalized top-level schema by building its complete mapping (settings
            # + properties + dynamic templates) before registration, so a broken plugin extension
            # or schema regression fails loudly at datastore startup rather than at first index
            # access/reconciliation.
            new_schema.document_mapping(finalized)
            finalized_schema_models[_index] = finalized

        for _index in INDEXES:
            ilm_index_config = config.datastore.ilm.indices.get(_index)
            if ilm_index_config is None:
                ilm_index_config = ILMIndexConfig(enabled=_index in ILM_ENABLED_INDEXES)
            if not (config.datastore.ilm.enabled and ilm_index_config.enabled):
                ilm_index_config = None

            self.ds.register(
                _index,
                finalized_schema_models[_index],
                ilm_config=ilm_index_config,
                schema_model=finalized_schema_models[_index],
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds.close()

    def __getitem__(self, key: str):
        return self.ds[key]

    def stop_model_validation(self):
        self.ds.validate = False

    def start_model_validation(self):
        self.ds.validate = True

    def enable_archive_access(self):
        self.ds.archive_access = True

    def disable_archive_access(self):
        self.ds.archive_access = False

    @property
    def hit(self) -> ESCollection[Hit]:
        return self.ds.hit

    @property
    def event(self) -> ESCollection[Event]:
        return self.ds.event

    @property
    def case(self) -> ESCollection[Case]:
        return self.ds.case

    @property
    def template(self) -> ESCollection[Template]:
        return self.ds.template

    @property
    def overview(self) -> ESCollection[Overview]:
        return self.ds.overview

    @property
    def view(self) -> ESCollection[View]:
        return self.ds.view

    @property
    def analytic(self) -> ESCollection[Analytic]:
        return self.ds.analytic

    @property
    def action(self) -> ESCollection[Action]:
        return self.ds.action

    @property
    def user(self) -> ESCollection[User]:
        return self.ds.user

    @property
    def dossier(self) -> ESCollection[Dossier]:
        return self.ds.dossier

    @property
    def user_avatar(self) -> ESCollection:
        return self.ds.user_avatar

    def get_collection(self, collection_name: str) -> ESCollection:
        if collection_name in self.ds.get_models():
            return getattr(self, collection_name)
        else:
            raise HowlerAttributeError(f"Collection {collection_name} does not exist.")
