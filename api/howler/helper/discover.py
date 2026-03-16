import sys
from typing import Any, Optional

import requests

from howler.common.logging import get_logger
from howler.config import config

logger = get_logger(__file__)
DISCO_CACHE = {}


def get_apps_list(discovery_url: Optional[str]) -> list[dict[str, str]]:
    """Get a list of apps from the discovery service

    Returns:
        list[dict[str, str]]: A list of other apps
    """
    if discovery_url not in DISCO_CACHE:
        apps: list[dict[str, Any]] = []

        if "pytest" in sys.modules:
            logger.info("Skipping discovery, running in a test environment")

        url = discovery_url or config.ui.discover_url
        if not url:
            return apps

        try:
            resp = requests.get(
                url,
                headers={"accept": "application/json"},
                timeout=5,
            )

            if resp.ok:
                data = resp.json()
                for app in data["applications"]["application"]:
                    try:
                        app_url = app["instance"][0]["hostName"]
                        if "howler" not in app_url:
                            apps.append(
                                {
                                    "alt": app["instance"][0]["metadata"]["alternateText"],
                                    "name": app["name"],
                                    "img_d": app["instance"][0]["metadata"]["imageDark"],
                                    "img_l": app["instance"][0]["metadata"]["imageLight"],
                                    "route": app_url,
                                    "classification": app["instance"][0]["metadata"]["classification"],
                                }
                            )

                    except Exception:
                        logger.exception(f"Failed to parse get app: {str(app)}")
            else:
                logger.warning(f"Invalid response from server for apps discovery: {discovery_url}")
        except Exception:
            logger.exception(f"Failed to get apps from discover URL: {discovery_url}")

        DISCO_CACHE[discovery_url] = sorted(apps, key=lambda k: k["name"])
        return sorted(apps, key=lambda k: k["name"])
    else:
        return DISCO_CACHE[discovery_url]
