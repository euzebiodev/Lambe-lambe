"""
Abre o Lambe-lambe em uma janela de aplicativo.

Este launcher usa a interface Flask existente, mas inicia tudo localmente e
desativa a autenticacao HTTP Basic para uso no proprio computador.
"""

import os
import threading

from werkzeug.serving import make_server

os.environ.setdefault("POLAROID_DEV_NO_AUTH", "1")

from polaroid_web import app  # noqa: E402


class LocalServer:
    def __init__(self):
        self.server = make_server("127.0.0.1", 0, app, threaded=True)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()


def main():
    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "ERRO: instale as dependencias com: pip install -r requirements.txt"
        ) from exc

    server = LocalServer()
    server.start()

    try:
        webview.create_window(
            "Lambe-lambe",
            server.url,
            width=1240,
            height=860,
            min_size=(900, 640),
        )
        webview.start()
    finally:
        server.stop()


if __name__ == "__main__":
    main()
