"""
polaroid_web.py
---------------
Interface web para o polaroid_album.py.

Sobe um servidor local com pagina drag-and-drop. Voce escolhe ou arrasta
as fotos, reordena se quiser, define o nome do arquivo e baixa o .docx.

USO:
    python polaroid_web.py
    -> abre http://127.0.0.1:5000

REQUISITOS:
    pip install flask pillow python-docx opencv-python

OBS: o arquivo polaroid_album.py precisa estar na MESMA pasta deste script.
"""

import io
import logging
import os
import secrets
import sys
import tempfile
import time
import uuid
from functools import wraps
from pathlib import Path

try:
    from flask import Flask, Response, request, send_file, render_template_string
except ImportError:
    sys.exit("ERRO: instale o Flask com:  pip install flask")

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    sys.exit("ERRO: instale a Pillow com:  pip install pillow")

# Importa a logica de geracao do polaroid_album.py (mesma pasta).
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from polaroid_album import (
        gerar_polaroid,
        gerar_preview_foto_maquina,
        montar_documento,
        MODO_FOTO_MAQUINA,
        MODO_POLAROID,
    )
except ImportError:
    sys.exit("ERRO: nao achei polaroid_album.py na mesma pasta de polaroid_web.py")


HTML = r"""
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Album Polaroid</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #f4f1ec;
    margin: 0; padding: 32px 16px;
    min-height: 100vh;
    color: #2a2a2a;
  }
  .wrap { max-width: 1400px; margin: 0 auto; }
  h1 { margin: 0 0 4px; font-weight: 600; font-size: 28px; }
  p.sub { margin: 0 0 28px; color: #6b6b6b; }

  .drop {
    border: 2px dashed #b9b1a6;
    border-radius: 14px;
    background: #fff;
    padding: 56px 24px;
    text-align: center;
    transition: .15s;
    cursor: pointer;
  }
  .drop.hover { border-color: #2a2a2a; background: #fbf7f0; }
  .drop strong { display: block; font-size: 18px; margin-bottom: 6px; }
  .drop span  { color: #777; font-size: 14px; }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 16px;
    margin-top: 22px;
  }
  .card {
    background: #fff;
    border: 1px solid #e2dcd0;
    border-radius: 8px;
    padding: 8px 8px 6px;
    text-align: center;
    cursor: grab;
    user-select: none;
    position: relative;
    transition: transform .1s;
  }
  .card.drag { opacity: .4; }
  .card.over { transform: scale(1.04); border-color: #2a2a2a; }
  .preview-row {
    display: grid;
    grid-template-columns: 1fr 34px;
    gap: 8px;
    align-items: start;
  }
  .preview-box {
    width: 100%;
    overflow: hidden;
    border-radius: 4px;
    background: #fff;
  }
  .preview-box.pan-on {
    cursor: grab;
  }
  .preview-box.pan-on:active {
    cursor: grabbing;
  }
  .preview-box canvas {
    display: block;
    width: 100%;
    height: auto;
  }
  .tools {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .tool {
    width: 30px;
    height: 30px;
    border: 1px solid #cfc6b8;
    border-radius: 6px;
    background: #fbf8f2;
    color: #2a2a2a;
    font-weight: 700;
    cursor: pointer;
    line-height: 1;
  }
  .tool.active {
    background: #2a2a2a;
    color: #fff;
    border-color: #2a2a2a;
  }
  .card .name { font-size: 11px; color: #555; margin-top: 4px; word-break: break-all; }
  .card .x {
    position: absolute; top: 4px; right: 4px;
    width: 22px; height: 22px; border-radius: 50%;
    background: rgba(0,0,0,.55); color:#fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; line-height: 1;
    cursor: pointer;
  }
  .card .order {
    position: absolute; top: 4px; left: 4px;
    background: #2a2a2a; color:#fff;
    border-radius: 50%;
    width: 22px; height: 22px;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 600;
  }

  .controls {
    margin-top: 28px;
    background: #fff; border:1px solid #e2dcd0; border-radius: 12px;
    padding: 18px; display: flex; gap: 12px; align-items: center;
    flex-wrap: wrap;
  }
  .controls label { font-size: 14px; color: #444; }
  .controls input[type=text] {
    flex: 1; min-width: 200px;
    border: 1px solid #d6cfc1; border-radius: 8px;
    padding: 10px 12px; font-size: 14px; background:#fbf8f2;
  }
  .mode {
    display: inline-flex;
    border: 1px solid #c9c1b3;
    border-radius: 8px;
    overflow: hidden;
    background: #fbf8f2;
  }
  .mode input { position: absolute; opacity: 0; pointer-events: none; }
  .mode label {
    padding: 10px 12px;
    min-width: 118px;
    text-align: center;
    cursor: pointer;
    color: #3f3a34;
    border-right: 1px solid #c9c1b3;
  }
  .mode label:last-child { border-right: 0; }
  .mode input:checked + label {
    background: #2a2a2a;
    color: #fff;
  }
  .btn {
    background: #2a2a2a; color: #fff;
    border: 0; padding: 11px 22px; border-radius: 8px;
    font-size: 14px; cursor: pointer; font-weight: 600;
  }
  .btn:disabled { opacity: .4; cursor: not-allowed; }
  .btn.ghost { background: transparent; color:#2a2a2a; border:1px solid #c9c1b3; }

  .status { margin-top: 16px; font-size: 13px; color: #555; min-height: 20px; }
  .status.err { color: #b3261e; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Album Polaroid</h1>
  <p class="sub">Solte ou escolha suas fotos. Arraste os cards para reordenar. O documento sai com 3 polaroids por linha em uma pagina A4 com linha de corte clara.</p>

  <div id="drop" class="drop">
    <strong>Arraste as fotos aqui</strong>
    <span>ou clique para escolher (jpg, png) - multiplas permitidas</span>
    <input id="picker" type="file" accept="image/*" multiple hidden>
  </div>

  <div id="grid" class="grid"></div>

  <div class="controls">
    <div class="mode" aria-label="Modo do documento">
      <input id="modoPolaroid" name="modo" type="radio" value="polaroid" checked>
      <label for="modoPolaroid">Polaroid</label>
      <input id="modoMaquina" name="modo" type="radio" value="foto_maquina">
      <label for="modoMaquina">Foto maquina</label>
    </div>
    <label for="nome">Nome do arquivo:</label>
    <input id="nome" type="text" value="album_polaroid.docx" />
    <button id="btnLimpar" class="btn ghost" type="button">Limpar</button>
    <button id="btnGerar" class="btn" type="button" disabled>Gerar e baixar</button>
  </div>

  <div id="status" class="status"></div>
</div>

<script>
const drop   = document.getElementById('drop');
const picker = document.getElementById('picker');
const grid   = document.getElementById('grid');
const btnGerar = document.getElementById('btnGerar');
const btnLimpar = document.getElementById('btnLimpar');
const nome   = document.getElementById('nome');
const status = document.getElementById('status');

let arquivos = []; // [{file, url, img, zoom, panX, panY, panMode}]
let dragIdx = null;
let panState = null;

function modoAtual() {
  return document.querySelector('input[name="modo"]:checked').value;
}

function dimensoesFoto() {
  if (modoAtual() === 'foto_maquina') return { w: 708, h: 552 };
  return { w: 800, h: 1000 };
}

function desenharFoto(ctx, item, x, y, w, h) {
  if (!item.img || !item.img.complete) return;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();

  const base = item.fitAll
    ? Math.min(w / item.img.naturalWidth, h / item.img.naturalHeight)
    : Math.max(w / item.img.naturalWidth, h / item.img.naturalHeight);
  const escala = base * item.zoom;
  const dw = item.img.naturalWidth * escala;
  const dh = item.img.naturalHeight * escala;
  const dx = x + (w - dw) / 2 + item.panX;
  const dy = y + (h - dh) / 2 + item.panY;
  ctx.drawImage(item.img, dx, dy, dw, dh);
  ctx.restore();
}

function desenharPreview(canvas, item) {
  const ctx = canvas.getContext('2d');
  if (modoAtual() === 'foto_maquina') {
    canvas.width = 708;
    canvas.height = 552;
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    desenharFoto(ctx, item, 0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#d7d7d7';
    ctx.lineWidth = 2;
    ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
    return;
  }

  canvas.width = 928;
  canvas.height = 1288;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.shadowColor = 'rgba(0,0,0,.24)';
  ctx.shadowBlur = 18;
  ctx.shadowOffsetX = 12;
  ctx.shadowOffsetY = 12;
  ctx.fillStyle = '#fff';
  ctx.fillRect(24, 24, 880, 1240);
  ctx.shadowColor = 'transparent';
  desenharFoto(ctx, item, 64, 64, 800, 1000);
  ctx.strokeStyle = '#d7d7d7';
  ctx.lineWidth = 2;
  ctx.strokeRect(24, 24, 880, 1240);
}

function limitarPan(item) {
  if (!item.img) return;
  const d = dimensoesFoto();
  const base = item.fitAll
    ? Math.min(d.w / item.img.naturalWidth, d.h / item.img.naturalHeight)
    : Math.max(d.w / item.img.naturalWidth, d.h / item.img.naturalHeight);
  const dw = item.img.naturalWidth * base * item.zoom;
  const dh = item.img.naturalHeight * base * item.zoom;
  const maxX = Math.max(0, (dw - d.w) / 2);
  const maxY = Math.max(0, (dh - d.h) / 2);
  item.panX = Math.max(-maxX, Math.min(maxX, item.panX));
  item.panY = Math.max(-maxY, Math.min(maxY, item.panY));
}

function renderizarTudo() {
  document.querySelectorAll('canvas[data-idx]').forEach(canvas => {
    const item = arquivos[Number(canvas.dataset.idx)];
    if (item) desenharPreview(canvas, item);
  });
}

function alterarZoom(item, delta) {
  item.zoom = Math.max(1, Math.min(3, Math.round((item.zoom + delta) * 10) / 10));
  limitarPan(item);
  renderizarTudo();
}

function alternarCabertudo(item) {
  item.fitAll = !item.fitAll;
  item.zoom = 1;
  item.panX = 0;
  item.panY = 0;
  renderizarTudo();
  refresh();
}

function restaurar(item) {
  item.zoom = 1;
  item.panX = 0;
  item.panY = 0;
  item.panMode = false;
  item.fitAll = false;
  refresh();
}

function canvasParaBlob(canvas) {
  return new Promise(resolve => canvas.toBlob(resolve, 'image/png', 0.95));
}

async function imagemEnquadrada(item) {
  if (item.img && !item.img.complete && item.img.decode) {
    try { await item.img.decode(); } catch (err) {}
  }
  const d = dimensoesFoto();
  const canvas = document.createElement('canvas');
  canvas.width = d.w;
  canvas.height = d.h;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, d.w, d.h);
  desenharFoto(ctx, item, 0, 0, d.w, d.h);
  return canvasParaBlob(canvas);
}

function refresh() {
  grid.innerHTML = '';
  grid.className = 'grid mode-' + modoAtual();
  arquivos.forEach((a, i) => {
    const card = document.createElement('div');
    card.className = 'card';
    card.draggable = !a.panMode;
    card.dataset.idx = i;
    card.innerHTML = `
      <div class="order">${i+1}</div>
      <div class="x" title="Remover">&times;</div>
      <div class="preview-row">
        <div class="preview-box ${a.panMode ? 'pan-on' : ''}">
          <canvas data-idx="${i}"></canvas>
        </div>
        <div class="tools">
          <button class="tool zoom-in" type="button" title="Zoom mais">+</button>
          <button class="tool zoom-out" type="button" title="Zoom menos">-</button>
          <button class="tool pan ${a.panMode ? 'active' : ''}" type="button" title="Mover enquadramento">✋</button>
          <button class="tool fit ${a.fitAll ? 'active' : ''}" type="button" title="Mostrar imagem original inteira">□</button>
          <button class="tool reset" type="button" title="Restaurar original">↺</button>
        </div>
      </div>
      <div class="name"></div>
    `;
    card.querySelector('.name').textContent = a.file.name;
    card.querySelector('.x').addEventListener('click', e => {
      e.stopPropagation();
      URL.revokeObjectURL(a.url);
      arquivos.splice(i, 1); refresh();
    });
    card.querySelectorAll('.tool').forEach(btn => {
      btn.addEventListener('pointerdown', e => e.stopPropagation());
    });
    card.querySelector('.zoom-in').addEventListener('click', e => {
      e.stopPropagation(); alterarZoom(a, 0.1);
    });
    card.querySelector('.zoom-out').addEventListener('click', e => {
      e.stopPropagation(); alterarZoom(a, -0.1);
    });
    card.querySelector('.pan').addEventListener('click', e => {
      e.stopPropagation();
      a.panMode = !a.panMode;
      refresh();
    });
    card.querySelector('.fit').addEventListener('click', e => {
      e.stopPropagation(); alternarCabertudo(a);
    });
    card.querySelector('.reset').addEventListener('click', e => {
      e.stopPropagation(); restaurar(a);
    });
    const canvas = card.querySelector('canvas');
    const previewBox = card.querySelector('.preview-box');
    previewBox.addEventListener('pointerdown', e => {
      if (!a.panMode || a.zoom <= 1) return;
      e.preventDefault();
      e.stopPropagation();
      const rect = canvas.getBoundingClientRect();
      const d = dimensoesFoto();
      panState = {
        item: a,
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        panX: a.panX,
        panY: a.panY,
        scaleX: d.w / rect.width,
        scaleY: d.h / rect.height,
      };
      previewBox.setPointerCapture(e.pointerId);
    });
    previewBox.addEventListener('pointermove', e => {
      if (!panState || panState.item !== a) return;
      a.panX = panState.panX + (e.clientX - panState.startX) * panState.scaleX;
      a.panY = panState.panY + (e.clientY - panState.startY) * panState.scaleY;
      limitarPan(a);
      renderizarTudo();
    });
    previewBox.addEventListener('pointerup', e => {
      if (panState && panState.pointerId === e.pointerId) panState = null;
    });
    previewBox.addEventListener('pointercancel', () => { panState = null; });
    card.addEventListener('dragstart', e => {
      if (a.panMode) {
        e.preventDefault();
        return;
      }
      dragIdx = i; card.classList.add('drag');
      e.dataTransfer.effectAllowed = 'move';
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('drag');
      document.querySelectorAll('.card.over').forEach(c => c.classList.remove('over'));
    });
    card.addEventListener('dragover', e => {
      e.preventDefault();
      if (dragIdx !== null && dragIdx !== i) card.classList.add('over');
    });
    card.addEventListener('dragleave', () => card.classList.remove('over'));
    card.addEventListener('drop', e => {
      e.preventDefault();
      if (dragIdx === null || dragIdx === i) return;
      const it = arquivos.splice(dragIdx, 1)[0];
      arquivos.splice(i, 0, it);
      dragIdx = null;
      refresh();
    });
    grid.appendChild(card);
    desenharPreview(canvas, a);
  });
  btnGerar.disabled = arquivos.length === 0;
}

function adicionar(files) {
  for (const f of files) {
    if (!f.type.startsWith('image/')) continue;
    const item = {
      file: f,
      url: URL.createObjectURL(f),
      img: null,
      zoom: 1,
      panX: 0,
      panY: 0,
      panMode: false,
      fitAll: false,
    };
    item.img = new Image();
    item.img.onload = renderizarTudo;
    item.img.src = item.url;
    arquivos.push(item);
  }
  refresh();
}

document.querySelectorAll('input[name="modo"]').forEach(r => {
  r.addEventListener('change', () => {
    refresh();
  });
});

drop.addEventListener('click', () => picker.click());
picker.addEventListener('change', e => adicionar(e.target.files));

['dragenter','dragover'].forEach(ev =>
  drop.addEventListener(ev, e => {
    // so destaca drop quando o drag vem de fora (arquivos), nao reordenacao de cards
    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
      e.preventDefault(); drop.classList.add('hover');
    }
  })
);
['dragleave','drop'].forEach(ev =>
  drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('hover'); })
);
drop.addEventListener('drop', e => {
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
    adicionar(e.dataTransfer.files);
  }
});

btnLimpar.addEventListener('click', () => {
  arquivos.forEach(a => {
    URL.revokeObjectURL(a.url);
  });
  arquivos = []; refresh();
  status.className = 'status'; status.textContent = '';
});

btnGerar.addEventListener('click', async () => {
  if (!arquivos.length) return;
  status.className = 'status';
  status.textContent = 'Gerando documento...';
  btnGerar.disabled = true;

  const fd = new FormData();
  let saida = (nome.value || 'album_polaroid.docx').trim();
  if (!saida.toLowerCase().endsWith('.docx')) saida += '.docx';
  fd.append('saida', saida);
  fd.append('modo', document.querySelector('input[name="modo"]:checked').value);

  try {
    for (let i = 0; i < arquivos.length; i++) {
      const blob = await imagemEnquadrada(arquivos[i]);
      const base = arquivos[i].file.name.replace(/\.[^.]+$/, '') || ('img_' + i);
      fd.append('imagens', blob, base + '_enquadrada.png');
    }
    const r = await fetch('/gerar', { method: 'POST', body: fd });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || ('HTTP ' + r.status));
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = saida;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    status.textContent = 'Pronto! Arquivo baixado.';
  } catch (err) {
    status.className = 'status err';
    status.textContent = 'Erro: ' + err.message;
  } finally {
    btnGerar.disabled = arquivos.length === 0;
  }
});
</script>
</body>
</html>
"""

app = Flask(__name__)


def _env_int(name, default, minimum=1):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        logging.warning("Valor invalido para %s=%r; usando %s.", name, value, default)
        return default
    if parsed < minimum:
        logging.warning("Valor abaixo do minimo para %s=%r; usando %s.", name, value, default)
        return default
    return parsed


app.config["MAX_CONTENT_LENGTH"] = _env_int("POLAROID_MAX_UPLOAD_MB", 50) * 1024 * 1024

MAX_FILES = _env_int("POLAROID_MAX_FILES", 60)
MAX_IMAGE_PIXELS = _env_int("POLAROID_MAX_IMAGE_PIXELS", 24000000)
RATE_LIMIT_REQUESTS = _env_int("POLAROID_RATE_LIMIT_REQUESTS", 60)
RATE_LIMIT_WINDOW = _env_int("POLAROID_RATE_LIMIT_WINDOW", 60)
PASSWORD = os.environ.get("POLAROID_PASSWORD")
DEV_NO_AUTH = os.environ.get("POLAROID_DEV_NO_AUTH") == "1"
TRUST_PROXY = os.environ.get("POLAROID_TRUST_PROXY") == "1"
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_RATE_LIMIT = {}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if TRUST_PROXY and forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def _rate_limit_key():
    auth = request.authorization
    user = auth.username if auth else "-"
    return f"{_client_ip()}:{user}:{request.endpoint}"


def _check_rate_limit():
    now = time.monotonic()
    key = _rate_limit_key()
    bucket = [ts for ts in _RATE_LIMIT.get(key, []) if now - ts < RATE_LIMIT_WINDOW]
    if len(bucket) >= RATE_LIMIT_REQUESTS:
        return False
    bucket.append(now)
    _RATE_LIMIT[key] = bucket
    return True


def _unauthorized():
    return Response(
        "Autenticacao obrigatoria.",
        401,
        {"WWW-Authenticate": 'Basic realm="Album Polaroid"'},
    )


def require_auth(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _check_rate_limit():
            return ("Muitas requisicoes. Tente novamente em instantes.", 429)

        if DEV_NO_AUTH and _client_ip() in {"127.0.0.1", "::1", "localhost"}:
            return view(*args, **kwargs)

        if not PASSWORD:
            return ("Servidor sem POLAROID_PASSWORD configurado.", 503)

        auth = request.authorization
        if not auth or auth.username != "admin" or not secrets.compare_digest(auth.password, PASSWORD):
            return _unauthorized()

        return view(*args, **kwargs)

    return wrapper


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


def _safe_download_name(name):
    base = Path(name or "album_polaroid.docx").name.strip().replace("\x00", "")
    if not base:
        base = "album_polaroid.docx"
    if not base.lower().endswith(".docx"):
        base += ".docx"
    safe = "".join(ch for ch in base if ch.isalnum() or ch in " ._-")[:120]
    stem = safe[:-5] if safe.lower().endswith(".docx") else safe
    if not safe or not any(ch.isalnum() for ch in stem):
        return "album_polaroid.docx"
    return safe


def _save_valid_image(file_storage, directory, index=0):
    target = os.path.join(directory, f"upload_{index}_{uuid.uuid4().hex}.img")
    file_storage.save(target)

    try:
        with Image.open(target) as img:
            img.verify()
        with Image.open(target) as img:
            if img.format not in ALLOWED_FORMATS:
                raise ValueError("Formato de imagem nao permitido.")
            if img.width <= 0 or img.height <= 0 or img.width * img.height > MAX_IMAGE_PIXELS:
                raise ValueError("Imagem grande demais.")
            if getattr(img, "is_animated", False):
                raise ValueError("Imagens animadas nao sao permitidas.")
    except (UnidentifiedImageError, OSError, ValueError) as e:
        try:
            os.remove(target)
        except OSError:
            pass
        raise ValueError(str(e) or "Imagem invalida.") from e

    return target


@app.route("/")
@require_auth
def index():
    return render_template_string(HTML)


@app.route("/preview", methods=["POST"])
@require_auth
def preview():
    arquivo = request.files.get("imagem")
    if not arquivo:
        return ("Nenhuma imagem enviada.", 400)

    modo = (request.form.get("modo") or MODO_POLAROID).strip()
    if modo not in (MODO_POLAROID, MODO_FOTO_MAQUINA):
        return ("Modo invalido.", 400)

    with tempfile.TemporaryDirectory() as td:
        try:
            caminho = _save_valid_image(arquivo, td)
            if modo == MODO_FOTO_MAQUINA:
                png = gerar_preview_foto_maquina(caminho)
            else:
                png = gerar_polaroid(caminho)
        except ValueError as e:
            return (f"Imagem recusada: {e}", 400)
        except Exception:
            app.logger.exception("Falha ao gerar preview.")
            return ("Falha ao gerar preview.", 500)

    buf = io.BytesIO(png)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@app.route("/gerar", methods=["POST"])
@require_auth
def gerar():
    arquivos = request.files.getlist("imagens")
    if not arquivos:
        return ("Nenhuma imagem enviada.", 400)
    if len(arquivos) > MAX_FILES:
        return (f"Limite de {MAX_FILES} imagens por documento.", 400)

    saida_nome = _safe_download_name(request.form.get("saida"))
    modo = (request.form.get("modo") or MODO_POLAROID).strip()
    if modo not in (MODO_POLAROID, MODO_FOTO_MAQUINA):
        return ("Modo invalido.", 400)

    with tempfile.TemporaryDirectory() as td:
        caminhos = []
        try:
            for idx, fs in enumerate(arquivos):
                caminhos.append(_save_valid_image(fs, td, idx))
        except ValueError as e:
            return (f"Imagem recusada: {e}", 400)

        saida_path = os.path.join(td, "saida.docx")
        try:
            montar_documento(caminhos, saida_path, modo=modo)
        except Exception:
            app.logger.exception("Falha ao gerar documento.")
            return ("Falha ao gerar documento.", 500)

        with open(saida_path, "rb") as f:
            buf = io.BytesIO(f.read())
        buf.seek(0)
        return send_file(
            buf,
            as_attachment=True,
            download_name=saida_nome,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )


if __name__ == "__main__":
    print("=" * 56)
    print(" Album Polaroid - interface web")
    print(" Abra no navegador:  http://127.0.0.1:5000")
    print(" (ctrl+c para encerrar)")
    print("=" * 56)
    app.run(host="127.0.0.1", port=5000, debug=False)
