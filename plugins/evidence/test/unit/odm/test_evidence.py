from types import SimpleNamespace

import pytest
from howler.common.exceptions import HowlerValueError
from howler.models import model_extensions
from howler.models.hit import Hit
from howler.services import hit_service

from evidence.models.hit import declare_hit_extension


@pytest.fixture
def registered_hit(monkeypatch):
    model_extensions.clear()
    declare_hit_extension()
    hit_type = model_extensions.finalize(Hit)
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=hit_type)))
    yield
    model_extensions.clear()


def test_build_evidence_alert(registered_hit):
    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "Evidence Example Analytic",
            "evidence.agent.id": ["potato"],
        },
        unique=False,
    )

    assert hit.evidence[0].agent.id == "potato"

    assert len(warnings) == 0

    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "Evidence Example Analytic Part Two",
            "evidence": [{"agent.id": "potato"}, {"agent.id": "potato"}],
        },
        unique=False,
    )

    assert hit.evidence[0].agent.id == "potato"

    assert len(warnings) == 0

    with pytest.raises(HowlerValueError) as err:
        hit_service.convert_hit(
            {
                "howler.analytic": "Evidence Example Analytic Part Two",
                "evidence": [{"agent.id": "potato"}, {"agent.nope": "potato"}],
            },
            unique=False,
        )

    assert "nope" in str(err)
