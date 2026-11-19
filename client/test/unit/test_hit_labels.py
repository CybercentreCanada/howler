from unittest.mock import MagicMock

import pytest

from howler_client.common.utils import ClientError
from howler_client.module.hit import Hit


@pytest.mark.parametrize(("method", "verb"), [("add_label", "put"), ("remove_label", "delete")])
@pytest.mark.parametrize(
    ("labels", "expected", "kwargs", "refresh"),
    [
        ("reviewed", ["reviewed"], {}, "False"),
        (["reviewed", "triaged"], ["reviewed", "triaged"], {"refresh": "wait_for"}, "wait_for"),
    ],
)
def test_hit_label_request(method, verb, labels, expected, kwargs, refresh):
    connection = MagicMock()
    request = getattr(connection, verb)
    request.return_value = {"howler": {"id": "hit-1", "labels": {"generic": ["reviewed"]}}}
    hit = Hit(connection, MagicMock())

    result = getattr(hit, method)("hit-1", "generic", labels, **kwargs)

    request.assert_called_once_with(f"api/v1/hit/hit-1/labels/generic?refresh={refresh}", json={"value": expected})
    assert result is request.return_value


@pytest.mark.parametrize(("method", "verb"), [("add_label", "put"), ("remove_label", "delete")])
@pytest.mark.parametrize("status", [400, 404])
def test_hit_label_propagates_client_error(method, verb, status):
    connection = MagicMock()
    error = ClientError("Label request failed", status)
    getattr(connection, verb).side_effect = error
    hit = Hit(connection, MagicMock())

    with pytest.raises(ClientError) as exc:
        getattr(hit, method)("hit-1", "generic", "reviewed")

    assert exc.value is error
