import importlib
from typing import Any, Callable, Optional

import chevron
import requests
from flask import request

from howler.common.exceptions import AuthenticationException, HowlerRuntimeError, HowlerValueError
from howler.common.logging import get_logger
from howler.config import cache, config
from howler.odm.models.analytic import Analytic

logger = get_logger(__file__)


@cache.memoize(15 * 60)
def get_token(access_token: str) -> str:
    """Get a notebook token based on the current howler token"""
    get_notebook_token: Optional[Callable[[str], str]] = None

    for plugin in config.core.plugins:
        try:
            module = importlib.import_module(f"{plugin}.token.notebook")

            get_notebook_token = module.get_notebook_token
            break
        except ImportError:
            logger.info("Plugin %s does not modify the notebook access token.")

    if get_notebook_token:
        notebook_access_token = get_notebook_token(access_token)
    else:
        logger.info("No custom notebook token logic provided, continuing with howler credentials")
        notebook_access_token = access_token

    return notebook_access_token


def get_nbgallery_nb(link: str):
    """Get a notebook from a given nbgallery link"""
    # /notebooks/1-example-nb
    # get the id (1)
    nb_id = link.rsplit("/", 1)[-1].rsplit("-")[0]
    auth_data: Optional[str] = request.headers.get("Authorization", None, type=str)

    if not auth_data:
        raise AuthenticationException("No Authorization header present")

    access_token = get_token(auth_data.split(" ")[1])

    # use obo token to retrieve notebook value
    notebook_req = requests.get(
        f"{config.core.notebook.url}/notebooks/{nb_id}/download.json",
        headers={
            "accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        timeout=5,
    )

    if notebook_req.ok:
        notebook: dict[str, Any] = notebook_req.json()

        name = notebook["metadata"]["gallery"]["title"]

        return (notebook, name)
    else:
        return None, None


def get_user_envs():
    """Get a user's environments from nbgallery"""
    auth_data: Optional[str] = request.headers.get("Authorization", None, type=str)

    if not auth_data:
        raise AuthenticationException("No Authorization header present")

    access_token = auth_data.split(" ")[1]

    for plugin in config.core.plugins:
        try:
            importlib.import_module(f"{plugin}.token.notebook").get_notebook_token(access_token)
            break
        except (ImportError, AttributeError):
            pass

    # get environment info from jupyterhub
    # how to get environment without nbgallery?
    # https://nbgallery.dev.analysis.cyber.gc.ca/environments.json
    env = requests.get(
        f"{config.core.notebook.url}/environments.json",
        headers={
            "accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        timeout=5,
    )

    if env.ok:
        env = env.json()
    else:
        raise HowlerRuntimeError(f"NBGallery returned {env.status_code}")

    return env


def get_nb_information(nb_link: str, analytic: Analytic, hit: dict[str, Any]):
    """Get a information about a notebook from nbgallery"""
    # get notebook
    # only from nbgallery for now
    if "nbgallery" in nb_link:
        json_content, name = get_nbgallery_nb(nb_link)
    else:
        raise HowlerValueError("Invalid notebook source")

    if not json_content or not name:
        raise HowlerRuntimeError("An error occurred when retrieving the notebook")

    try:
        # patch first node containing code with hit/analytic info
        cell_to_template = next(filter(lambda cell: cell["cell_type"] == "code", json_content["cells"]))
        # goal: support any field from a hit/analytic object
        cell_to_template["source"] = chevron.render(cell_to_template["source"], {"hit": hit, "analytic": analytic})
    except StopIteration as e:
        raise HowlerValueError("Notebook doesn't contain a cell with code.", e)
    except Exception as e:
        raise HowlerRuntimeError("Unexpected error while processing notebook.", e)

    return (json_content, name)
