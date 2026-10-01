"""Safe static messages for domain constraints remain useful to API clients."""

import pytest

from howler.models import HowlerModelValidationError
from howler.models.base import _public_error_message
from howler.models.case import CaseItem, CaseRule


def test_rule_expiry_message_is_preserved_without_echoing_input() -> None:
    with pytest.raises(HowlerModelValidationError, match="expire after resolved") as raised:
        CaseRule.validate_howler(
            {
                "rule_id": "rule-1",
                "destination": "folder",
                "query": "howler.id:*",
                "author": "analyst",
                "timeframe": None,
                "expire_after_resolved": True,
            }
        )
    assert str(raised.value).startswith("[caserule] ")
    assert raised.value.errors and raised.value.cause is not None


def test_rule_timeframe_message_is_preserved() -> None:
    with pytest.raises(HowlerModelValidationError, match="positive integer"):
        CaseRule.validate_howler(
            {"rule_id": "rule-1", "destination": "folder", "query": "q", "author": "a", "timeframe": -1}
        )


def test_case_item_root_constraint_message_is_preserved() -> None:
    with pytest.raises(HowlerModelValidationError, match="root-level"):
        CaseItem.validate_howler({"type": "case", "parent": "folder", "value": "case-1"})


def test_domain_message_whitelist_does_not_accept_untrusted_suffixes() -> None:
    assert (
        _public_error_message(
            {
                "type": "value_error",
                "msg": "Value error, Rule cannot expire after resolved when no timeframe is set SECRET",
            }
        )
        == "Invalid value"
    )
