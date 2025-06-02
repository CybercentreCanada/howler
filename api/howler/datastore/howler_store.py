import time
from typing import TYPE_CHECKING

import elasticapm
import elasticsearch

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

if TYPE_CHECKING:
    from howler.datastore.store import ESStore


class HowlerDatastore(object):
    def __init__(self, datastore_object: "ESStore"):
        self.ds = datastore_object
        self.ds.register("hit", Hit)
        self.ds.register("template", Template)
        self.ds.register("overview", Overview)
        self.ds.register("analytic", Analytic)
        self.ds.register("action", Action)
        self.ds.register("user", User)
        self.ds.register("view", View)
        self.ds.register("dossier", Dossier)
        self.ds.register("user_avatar")

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

    @elasticapm.capture_span(span_type="datastore")
    def multi_index_bulk(self, bulk_plans):
        max_retry_backoff = 10
        retries = 0
        while True:
            try:
                plan = "\n".join([p.get_plan_data() for p in bulk_plans])
                ret_val = self.ds.client.bulk(body=plan)  # type: ignore[call-arg]
                return ret_val
            except (
                elasticsearch.exceptions.ConnectionError,
                elasticsearch.exceptions.ConnectionTimeout,
                elasticsearch.exceptions.AuthenticationException,
            ):
                logger.warning(
                    f"No connection to Elasticsearch server(s): "
                    f"{' | '.join(self.ds.get_hosts(safe=True))}"
                    f", retrying..."
                )
                time.sleep(min(retries, max_retry_backoff))
                self.ds.connection_reset()
                retries += 1

            except elasticsearch.exceptions.TransportError as e:
                err_code, msg, cause = e.args
                if err_code == 503 or err_code == "503":
                    logger.warning("Looks like index is not ready yet, retrying...")
                    time.sleep(min(retries, max_retry_backoff))
                    self.ds.connection_reset()
                    retries += 1
                elif err_code == 429 or err_code == "429":
                    logger.warning(
                        "Elasticsearch is too busy to perform the requested task, " "we will wait a bit and retry..."
                    )
                    time.sleep(min(retries, max_retry_backoff))
                    self.ds.connection_reset()
                    retries += 1

                else:
                    raise
