import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def image_file(tmp_path):
    def create(name="foto.jpg", size=(320, 240), color=(80, 120, 180), fmt=None):
        path = tmp_path / name
        image = Image.new("RGB", size, color)
        image.save(path, format=fmt or path.suffix.lstrip(".").upper().replace("JPG", "JPEG"))
        return path

    return create


@pytest.fixture
def image_upload():
    def create(name="foto.jpg", size=(120, 90), color=(200, 60, 80), fmt="JPEG"):
        buf = io.BytesIO()
        Image.new("RGB", size, color).save(buf, format=fmt)
        buf.seek(0)
        return buf, name

    return create
