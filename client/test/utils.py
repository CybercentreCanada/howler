import datetime
import hashlib
import random
import time


def create_hit_and_get_id(client):
    map = {
        "file.sha256": ["file.hash.sha256", "howler.hash"],
        "file.name": ["file.name"],
        "src_ip": ["source.ip", "related.ip"],
        "dest_ip": ["destination.ip", "related.ip"],
        "time.created": ["event.start"],
        "time.completed": ["event.end"],
    }
    hits = []
    hits.append(
        {
            "src_ip": "43.228.141.216",
            "dest_ip": "31.46.39.115",
            "file": {
                "name": "cool_file.exe",
                "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            },
            "time": {
                "created": datetime.datetime(2020, 5, 17).isoformat() + "Z",
                "completed": datetime.datetime(2020, 5, 18).isoformat() + "Z",
            },
        }
    )
    hit_id = client.hit.create_from_map("tool_name", map, hits)[0]["id"]
    time.sleep(1)
    return hit_id


def random_hash():
    return hashlib.sha256(random.randbytes(128)).hexdigest()


def create_and_get_comment(client, comment_value: str):
    hit_to_update = client.search.hit("howler.id:*", rows=1)["items"][0]
    result = client.hit.comment.add(hit_to_update["howler"]["id"], comment_value)

    return result, next(
        (c for c in result["howler"]["comment"] if c["value"] == comment_value), None
    )
