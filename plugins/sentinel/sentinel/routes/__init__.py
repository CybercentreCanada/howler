from flask.blueprints import Blueprint

from sentinel.routes.ingest import sentinel_api

ROUTES: list[Blueprint] = [sentinel_api]
