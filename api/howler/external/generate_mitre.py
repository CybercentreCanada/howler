import json
import os
import sys
from pathlib import Path

import requests
import yaml


def run(writepath):
    """Run the script to generate mitre lookups"""
    dirname = Path(writepath)
    print(f"Generating mitre lookups to {dirname}")
    file_name = os.path.join(os.getcwd(), "enterprise-attack.json")
    tactics_name = dirname / "tactics.yml"
    techniques_name = dirname / "techniques.yml"

    if not os.path.exists(file_name):
        print("Pulling mitre attack data")
        response = requests.get(
            "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/"
            + "master/enterprise-attack/enterprise-attack.json",
            timeout=10,
        )

        response.raise_for_status()

        with open(file_name, "w") as f:
            f.write(response.text)

        print("Done!")

    print("Processing mitre attack data")
    with open(file_name, "r") as f:
        data = json.load(f)["objects"]

        tactics_list = sorted(
            [e for e in data if e["type"] == "x-mitre-tactic"],
            key=lambda x: x["external_references"][0]["external_id"],
        )

        tactics_list = [
            {
                "name": e["name"],
                "key": e["external_references"][0]["external_id"],
                "url": e["external_references"][0]["url"],
                # "description": e["description"].strip(),
            }
            for e in tactics_list
        ]

        tactics = {}
        for tactic in tactics_list:
            tactics[tactic["key"]] = tactic

        print(f"Writing tactics to {tactics_name}")
        with open(tactics_name, "w") as f:
            yaml.dump(tactics, f)

        techniques_list = sorted(
            [e for e in data if e["type"] == "attack-pattern"],
            key=lambda x: x["external_references"][0]["external_id"],
        )

        techniques_list = [
            {
                "name": e["name"],
                "key": e["external_references"][0]["external_id"],
                "url": e["external_references"][0]["url"],
                # "description": e["description"].strip(),
            }
            for e in techniques_list
        ]

        techniques = {technique["key"]: technique for technique in techniques_list}

        print(f"Writing techniques to {techniques_name}")
        with open(techniques_name, "w") as f:
            yaml.dump(techniques, f)

    print("Done!")


def main():
    "Main run function"
    writepath = None
    try:
        writepath = sys.argv[1]
    except Exception:
        writepath = "lookups"

    run(writepath)


if __name__ == "__main__":
    main()
