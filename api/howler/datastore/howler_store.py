from typing import TYPE_CHECKING

from howler.common.exceptions import HowlerAttributeError
from howler.datastore.collection import ESCollection, logger
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic
from howler.odm.models.dossier import Dossier
from howler.odm.models.hit import Hit
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.plugins import get_plugins

if TYPE_CHECKING:
    from howler.datastore.store import ESStore

INDEXES = [
    ("hit", Hit),
    ("template", Template),
    ("overview", Overview),
    ("analytic", Analytic),
    ("action", Action),
    ("user", User),
    ("view", View),
    ("dossier", Dossier),
    ("user_avatar", None),
]


class HowlerDatastore(object):
    def __init__(self, datastore_object: "ESStore"):
        self.ds = datastore_object

        for plugin in get_plugins():
            for _index, _odm in INDEXES:
                if _odm is None:
                    continue

                if modify_odm := plugin.modules.odm.modify_odm.get(_index):
                    logger.info("Modifying %s odm with function from plugin %s", _index, plugin.name)
                    modify_odm(_odm)

        for _index, _odm in INDEXES:
            self.ds.register(_index, _odm)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ds.close()

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
