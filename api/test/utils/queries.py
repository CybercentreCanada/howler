import random
from datetime import datetime, timedelta
from typing import Any, Optional, cast

from howler.odm import Model, flatten
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj


def get_value(_value) -> Optional[str]:
    if _value is None:
        return None

    if isinstance(_value, list):
        if len(_value) > 0:
            value = random.choice(_value)

            if isinstance(value, (list, dict)):
                return None

            if isinstance(value, bool):
                return str(value).lower()
            elif isinstance(value, (int, float)):
                return str(value)
            else:
                return f'"{str(value)}"'
        else:
            return None
    elif isinstance(_value, dict):
        return None
    elif isinstance(_value, bool):
        return str(_value).lower()
    elif isinstance(_value, (int, float)):
        return str(_value)
    else:
        return f'"{str(_value)}"'


def generate_lucene_query(hit: dict[str, Any], complexity=0):  # noqa: C901
    "Generate a random lucene query"
    data = flatten(hit, odm=Hit)

    alternative = flatten(random_model_obj(cast(Model, Hit)).as_primitives(), odm=Hit)

    queries: list[str] = []
    for key, _value in data.items():
        if key == "howler.data":
            continue

        if random.randint(0, 200 - complexity):
            continue

        value = get_value(_value)
        alt_value = get_value(alternative.get(key, None))

        if not value or not alt_value:
            continue

        sub_query = f"{key}:"
        try:
            start = (datetime.fromisoformat(value) - timedelta(days=1)).strftime("%Y-%m-%d")
            end = (datetime.fromisoformat(value) + timedelta(days=1)).strftime("%Y-%m-%d")
            sub_query += f"[{start} TO {end}]"
        except Exception:
            operator = random.choice(["", " AND ", " OR ", " OR ", " OR ", " OR "])

            options = [value, alt_value]  # type: ignore[arg-type]
            if not operator:
                sub_query += random.choice(options)
            else:
                joined = operator.join(options)

                sub_query += f"({joined})"

        queries.append(f"{sub_query}")

    query = ""
    for sub_query in queries:
        if not random.randint(0, 10) and query:
            query = f"({query}) {random.choice(['AND', 'OR'])} "
        elif query:
            query += random.choice([" AND ", " OR "])

        query += sub_query

    return query


if __name__ == "__main__":
    from howler.common.loader import datastore

    hit = datastore().hit.search("howler.id:*", rows=1, as_obj=False)["items"][0]

    print(generate_lucene_query(hit))  # noqa: T201
