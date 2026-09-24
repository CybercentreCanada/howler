"""Search index selection keeps the same access rules for Pydantic users."""

from howler.helper import search
from howler.models.user import User


def test_search_helpers_accept_pydantic_and_dictionary_users():
    user = User.validate_howler({"uname": "admin", "name": "Admin", "password": "hash", "type": ["admin"]})

    for value in (user, {"type": ["admin"]}):
        assert search.get_collection("hit", value) is search.INDEX_MAP["hit"]
        assert search.get_default_sort("hit", value) == "event.created desc"
