from howler.services import hit_service


def test_build_sentinel_alert():
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
            "howler.analytic": "Evidence Example Analytic 2",
            "evidence": [{"agent.id": "potato"}],
        },
        unique=False,
    )

    assert hit.evidence[0].agent.id == "potato"

    assert len(warnings) == 0
