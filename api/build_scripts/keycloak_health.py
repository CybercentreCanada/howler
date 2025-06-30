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
    try:
        response = requests.get("http://localhost:9100/health/ready")

        if response.ok:
            data = response.json()
            if data["status"] == "UP" and all(check["status"] == "UP" for check in data["checks"]):
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
    logging.info("Keycloak is healthy!")
else:
    logging.critical("Keycloak is unhealthy!")
    sys.exit(1)
