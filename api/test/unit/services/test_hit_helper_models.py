"""Hit workflow helpers keep stored operation values after the enum migration."""

import pytest

from howler.common.exceptions import InvalidDataException
from howler.helper import hit as hit_helper


def test_assess_hit_maps_new_enums_to_stored_operation_values():
    updates = {operation.key: operation.value for operation in hit_helper.assess_hit("attempt")}

    assert updates["howler.assessment"] == "attempt"
    assert updates["howler.escalation"] == "evidence"
    assert updates["howler.status"] == "resolved"


def test_assess_hit_rejects_unknown_values():
    with pytest.raises(InvalidDataException, match="Must set assessment"):
        hit_helper.assess_hit("unknown")
