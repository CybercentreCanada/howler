import pytest
from howler.common.exceptions import HowlerValueError
from howler.services import hit_service


def test_build_evidence_alert():
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
