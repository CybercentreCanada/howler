from howler.services import hit_service


def test_build_sentinel_alert():
    hit, warnings = hit_service.convert_hit(
        {"howler.analytic": "HBS Analytic", "sentinel.id": "Example Sentinel ID"},
        unique=False,
    )

    assert hit.sentinel.id == "Example Sentinel ID"

    assert len(warnings) == 0
