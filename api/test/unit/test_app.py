import howler.app as howler_app


def test_should_start_background_services(monkeypatch):
    """Workers start in production, serving, Gunicorn, and functional-test processes."""
    monkeypatch.setattr(howler_app, "DEBUG", True)
    monkeypatch.setattr(howler_app.sys, "argv", ["flask"])
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("HWL_START_BACKGROUND_SERVICES", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    assert not howler_app._should_start_background_services()

    monkeypatch.setenv("TESTING", "true")
    assert not howler_app._should_start_background_services()

    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    assert howler_app._should_start_background_services()

    monkeypatch.delenv("WERKZEUG_RUN_MAIN")
    monkeypatch.setenv("HWL_START_BACKGROUND_SERVICES", "true")
    assert howler_app._should_start_background_services()

    monkeypatch.delenv("HWL_START_BACKGROUND_SERVICES")
    monkeypatch.delenv("TESTING")
    monkeypatch.setattr(howler_app.sys, "argv", ["gunicorn"])
    assert howler_app._should_start_background_services()

    monkeypatch.setattr(howler_app, "DEBUG", False)
    monkeypatch.setattr(howler_app.sys, "argv", ["flask"])
    assert howler_app._should_start_background_services()
