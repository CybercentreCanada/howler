import howler.app as howler_app


def test_should_start_background_services(monkeypatch):
    """Workers start in production, serving, Gunicorn, and functional-test processes."""
    monkeypatch.setattr(howler_app, "DEBUG", True)
    monkeypatch.setattr(howler_app.sys, "argv", ["flask"])
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    assert not howler_app._should_start_background_services()

    monkeypatch.setenv("WERKZEUG_RUN_MAIN", "true")
    assert howler_app._should_start_background_services()

    monkeypatch.delenv("WERKZEUG_RUN_MAIN")
    monkeypatch.setenv("TESTING", "true")
    assert howler_app._should_start_background_services()

    monkeypatch.delenv("TESTING")
    monkeypatch.setattr(howler_app.sys, "argv", ["gunicorn"])
    assert howler_app._should_start_background_services()

    monkeypatch.setattr(howler_app, "DEBUG", False)
    monkeypatch.setattr(howler_app.sys, "argv", ["flask"])
    assert howler_app._should_start_background_services()
