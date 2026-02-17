import logging
import sys
import time
from http.client import RemoteDisconnected

import requests
import urllib3
import urllib3.exceptions

root = logging.getLogger()
root.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
root.addHandler(handler)

ready = False
retries = 0
while not ready and retries < 10:
    keycloak_ready = False
    elastic_ready = False
    try:
        keycloak = requests.get("http://localhost:9100/health/ready")

        if keycloak.ok:
            data = keycloak.json()
            if data["status"] == "UP" and all(check["status"] == "UP" for check in data["checks"]):
                keycloak_ready = True

        elastic = requests.get("http://localhost:9200/_cluster/health")

        if elastic.ok:
            data = elastic.json()
            if data["status"] == "green" and data["active_shards_percent_as_number"] >= 99.9:
                elastic_ready = True

        if keycloak_ready and elastic_ready:
            ready = True
            break
    except (
        ConnectionResetError,
        urllib3.exceptions.ProtocolError,
        RemoteDisconnected,
        requests.exceptions.ConnectionError,
    ):
        logging.warning("Failed to connect, retrying")
    except Exception:
        logging.exception("Exception on network call")

    retries += 1
    time.sleep(5)

if ready:
    logging.info("Keycloak and ES is healthy!")
else:
    logging.critical("Keycloak or ES is unhealthy!")
    sys.exit(1)
