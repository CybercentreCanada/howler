import json
import os

import pytest
from conftest import get_api_data

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import create_users_with_username
from howler.odm.random_data import create_hits, wipe_analytics, wipe_hits

usernames = ["donald", "huey", "louie", "dewey"]


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        create_users_with_username(datastore_connection, usernames)

        create_hits(datastore_connection, hit_count=10)

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)
        wipe_analytics(datastore_connection)


@pytest.mark.skip(reason="AL test - doesn't need to be run")
def test_pull_from_assemblyline(datastore: HowlerDatastore, login_session):
    from assemblyline_client import get_client as get_al_client

    user = os.getenv("AL_USER", None)
    apikey = os.getenv("AL_APIKEY", None)

    if not (user and apikey):
        pytest.skip("Assemblyline credentials required to run this test!")

    host = "https://malware-stg.cyber.gc.ca"

    al = get_al_client(host, apikey=(user, apikey))

    al_entries = al.alert.list(rows=1)
    al_alert = al_entries["items"][0]

    al_hwl_map = {
        "analytic": ["howler.analytic"],
        "org_name": ["organization.name"],
        "framework": ["threat.framework"],
        "tactic_id": ["threat.tactic.id"],
        "tactic_name": ["threat.tactic.name"],
        "scanner_stats": ["threat.indicator.scanner_stats"],
        "file.md5": ["related.hash", "file.hash.md5"],
        "file.sha1": ["related.hash", "file.hash.sha1"],
        "file.sha256": ["related.hash", "file.hash.sha256", "howler.hash"],
        "al.uri_static": ["related.uri"],
        "al.uri_dynamic": ["related.uri"],
        "al.domain_static": ["related.hosts"],
        "al.domain_dynamic": ["related.hosts"],
        "alert_id": ["related.id"],
        "file.name": ["file.name"],
        "file.size": ["file.size"],
        "file.mime_type": ["file.mime_type"],
        "al.detailed.av": ["assemblyline.antivirus"],
        "al.detailed.attrib": ["assemblyline.attribution"],
        "al.detailed.behavior": ["assemblyline.behaviour"],
        "al.detailed.uri": ["assemblyline.uri"],
        "al.detailed.domain": ["assemblyline.domain"],
        "al.detailed.yara": ["assemblyline.yara"],
        "al.detailed.heuristic": ["assemblyline.heuristic"],
        "al.detailed.attack_category": ["assemblyline.mitre.tactic"],
        "al.detailed.attack_pattern": ["assemblyline.mitre.technique"],
    }

    al_alert["analytic"] = "AssemblyLine"
    al_alert["org_name"] = al_alert["metadata"].get("ministerial_authority", "Unknown")
    al_alert["framework"] = "MITRE ATT&CK"
    al_alert["tactic_id"] = "TA0001"
    al_alert["tactic_name"] = "Initial Access"  # TODO: Use howler to populate this
    al_alert["scanner_stats"] = len(al_alert["verdict"]["malicious"])

    session, host = login_session
    get_api_data(
        session,
        f"{host}/api/v1/hit/assemblyline/",
        data=json.dumps({"map": al_hwl_map, "hits": [al_alert]}),
        method="POST",
    )
