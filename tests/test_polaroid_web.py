import base64
import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

import polaroid_web as web


@pytest.fixture(autouse=True)
def reset_web_state(monkeypatch):
    web._RATE_LIMIT.clear()
    monkeypatch.setattr(web, "DEV_NO_AUTH", True)
    monkeypatch.setattr(web, "PASSWORD", None)
    monkeypatch.setattr(web, "RATE_LIMIT_REQUESTS", 60)
    monkeypatch.setattr(web, "RATE_LIMIT_WINDOW", 60)
    yield
    web._RATE_LIMIT.clear()


@pytest.fixture
def client():
    web.app.config.update(TESTING=True)
    return web.app.test_client()


def basic_auth(password="secret"):
    token = base64.b64encode(f"admin:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_index_renders_app_page_and_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Album Polaroid" in response.data
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src" in response.headers["Content-Security-Policy"]


def test_safe_download_name_sanitizes_and_adds_docx():
    assert web._safe_download_name("../Album<>:Teste") == "AlbumTeste.docx"
    assert web._safe_download_name("") == "album_polaroid.docx"
    assert web._safe_download_name("ok.docx") == "ok.docx"
    assert web._safe_download_name("\x00") == "album_polaroid.docx"
    assert web._safe_download_name("<>") == "album_polaroid.docx"


def test_client_ip_prefers_forwarded_for(client):
    with web.app.test_request_context("/", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}):
        assert web._client_ip() == "1.2.3.4"


def test_rate_limit_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(web, "RATE_LIMIT_REQUESTS", 1)
    with web.app.test_request_context("/"):
        assert web._check_rate_limit() is True
        assert web._check_rate_limit() is False


def test_route_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(web, "RATE_LIMIT_REQUESTS", 0)

    response = client.get("/")

    assert response.status_code == 429


def test_requires_password_when_not_in_dev(client, monkeypatch):
    monkeypatch.setattr(web, "DEV_NO_AUTH", False)
    monkeypatch.setattr(web, "PASSWORD", None)

    response = client.get("/")

    assert response.status_code == 503


def test_rejects_bad_basic_auth(client, monkeypatch):
    monkeypatch.setattr(web, "DEV_NO_AUTH", False)
    monkeypatch.setattr(web, "PASSWORD", "secret")

    response = client.get("/", headers=basic_auth("wrong"))

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_accepts_good_basic_auth(client, monkeypatch):
    monkeypatch.setattr(web, "DEV_NO_AUTH", False)
    monkeypatch.setattr(web, "PASSWORD", "secret")

    response = client.get("/", headers=basic_auth("secret"))

    assert response.status_code == 200


def test_save_valid_image_accepts_real_image(tmp_path, image_upload):
    stream, name = image_upload()
    storage = FileStorage(stream=stream, filename=name, content_type="image/jpeg")

    saved = web._save_valid_image(storage, str(tmp_path))

    assert saved.endswith(".img")


def test_save_valid_image_rejects_invalid_file(tmp_path):
    storage = FileStorage(stream=io.BytesIO(b"not an image"), filename="x.jpg")

    with pytest.raises(ValueError):
        web._save_valid_image(storage, str(tmp_path))


def test_save_valid_image_ignores_cleanup_errors(tmp_path, monkeypatch):
    storage = FileStorage(stream=io.BytesIO(b"not an image"), filename="x.jpg")

    def fail_remove(_path):
        raise OSError("locked")

    monkeypatch.setattr(web.os, "remove", fail_remove)

    with pytest.raises(ValueError):
        web._save_valid_image(storage, str(tmp_path))


def test_save_valid_image_rejects_large_image(tmp_path, image_upload, monkeypatch):
    monkeypatch.setattr(web, "MAX_IMAGE_PIXELS", 10)
    stream, name = image_upload(size=(20, 20))
    storage = FileStorage(stream=stream, filename=name)

    with pytest.raises(ValueError, match="grande"):
        web._save_valid_image(storage, str(tmp_path))


def test_save_valid_image_rejects_disallowed_format(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="BMP")
    buf.seek(0)
    storage = FileStorage(stream=buf, filename="x.bmp")

    with pytest.raises(ValueError, match="Formato"):
        web._save_valid_image(storage, str(tmp_path))


def test_preview_requires_file(client):
    response = client.post("/preview")

    assert response.status_code == 400


def test_preview_rejects_invalid_mode(client, image_upload):
    stream, name = image_upload()

    response = client.post(
        "/preview",
        data={"modo": "x", "imagem": (stream, name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_preview_rejects_invalid_image(client):
    response = client.post(
        "/preview",
        data={"imagem": (io.BytesIO(b"bad"), "bad.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Imagem recusada" in response.data


def test_preview_returns_png(client, image_upload, monkeypatch):
    monkeypatch.setattr(web, "gerar_polaroid", lambda _path: b"png")
    stream, name = image_upload()

    response = client.post(
        "/preview",
        data={"modo": web.MODO_POLAROID, "imagem": (stream, name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.data == b"png"


def test_preview_returns_photo_booth_png(client, image_upload, monkeypatch):
    monkeypatch.setattr(web, "gerar_preview_foto_maquina", lambda _path: b"booth")
    stream, name = image_upload()

    response = client.post(
        "/preview",
        data={"modo": web.MODO_FOTO_MAQUINA, "imagem": (stream, name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.data == b"booth"


def test_preview_handles_generation_failure(client, image_upload, monkeypatch):
    def fail(_path):
        raise RuntimeError("boom")

    monkeypatch.setattr(web, "gerar_polaroid", fail)
    stream, name = image_upload()

    response = client.post(
        "/preview",
        data={"modo": web.MODO_POLAROID, "imagem": (stream, name)},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500


def test_gerar_requires_images(client):
    response = client.post("/gerar")

    assert response.status_code == 400


def test_gerar_rejects_too_many_files(client, image_upload, monkeypatch):
    monkeypatch.setattr(web, "MAX_FILES", 1)
    first = image_upload("a.jpg")
    second = image_upload("b.jpg")

    response = client.post(
        "/gerar",
        data={"imagens": [first, second]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_gerar_rejects_invalid_mode(client, image_upload):
    stream, name = image_upload()

    response = client.post(
        "/gerar",
        data={"modo": "x", "imagens": [(stream, name)]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_gerar_rejects_invalid_image(client):
    response = client.post(
        "/gerar",
        data={"imagens": [(io.BytesIO(b"bad"), "bad.jpg")]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert b"Imagem recusada" in response.data


def test_gerar_returns_docx(client, image_upload, monkeypatch, tmp_path):
    def fake_document(paths, output, modo):
        assert modo == web.MODO_POLAROID
        assert len(paths) == 1
        with open(output, "wb") as file:
            file.write(b"docx")

    monkeypatch.setattr(web, "montar_documento", fake_document)
    stream, name = image_upload()

    response = client.post(
        "/gerar",
        data={"saida": "saida", "modo": web.MODO_POLAROID, "imagens": [(stream, name)]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.data == b"docx"
    assert response.headers["Content-Disposition"].endswith('filename=saida.docx')


def test_gerar_handles_document_failure(client, image_upload, monkeypatch):
    def fail(_paths, _output, _modo):
        raise RuntimeError("boom")

    monkeypatch.setattr(web, "montar_documento", fail)
    stream, name = image_upload()

    response = client.post(
        "/gerar",
        data={"imagens": [(stream, name)]},
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
