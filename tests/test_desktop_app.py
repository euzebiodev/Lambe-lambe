import types

import pytest

import desktop_app


def test_local_server_start_and_stop():
    server = desktop_app.LocalServer()

    server.start()
    try:
        assert server.url.startswith("http://127.0.0.1:")
        assert server.thread.is_alive()
    finally:
        server.stop()


def test_main_opens_webview_and_stops_server(monkeypatch):
    events = []

    class FakeServer:
        url = "http://127.0.0.1:12345"

        def start(self):
            events.append("server-start")

        def stop(self):
            events.append("server-stop")

    fake_webview = types.SimpleNamespace(
        create_window=lambda *args, **kwargs: events.append(("window", args, kwargs)),
        start=lambda: events.append("webview-start"),
    )

    monkeypatch.setattr(desktop_app, "LocalServer", FakeServer)
    monkeypatch.setitem(__import__("sys").modules, "webview", fake_webview)

    desktop_app.main()

    assert events[0] == "server-start"
    assert events[1][0] == "window"
    assert events[2] == "webview-start"
    assert events[3] == "server-stop"


def test_main_reports_missing_webview(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "webview":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(SystemExit, match="instale as dependencias"):
        desktop_app.main()
