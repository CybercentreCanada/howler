from types import SimpleNamespace

import pytest
from howler.models import model_extensions
from howler.models.hit import Hit
from howler.services import hit_service

from sentinel.models.hit import declare_hit_extension


@pytest.fixture
def registered_hit(monkeypatch):
    model_extensions.clear()
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    yield
    model_extensions.clear()


def test_build_sentinel_alert(registered_hit):
    hit, warnings = hit_service.convert_hit(
        {"howler.analytic": "HBS Analytic", "sentinel.id": "Example Sentinel ID"},
        unique=False,
    )

    assert hit.sentinel.id == "Example Sentinel ID"

    assert len(warnings) == 0
