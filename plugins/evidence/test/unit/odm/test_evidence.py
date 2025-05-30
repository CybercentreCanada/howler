from howler.services import hit_service


def test_build_sentinel_alert():
    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "HBS Analytic",
            "evidence": [{"agent.id": "potato", "destination.ip": "1.1.1.1"}],
        },
        unique=False,
    )

    assert hit.evidence[0].agent.id == "potato"

    assert len(warnings) == 0
