# Deploy em producao

Este app nao deve ser publicado com `python polaroid_web.py`.
Use Gunicorn atras de Nginx/HTTPS.

## Variaveis obrigatorias

Defina uma senha forte:

```bash
export POLAROID_PASSWORD='uma-senha-grande-e-unica'
```

Opcionalmente ajuste limites:

```bash
export POLAROID_MAX_UPLOAD_MB=50
export POLAROID_MAX_FILES=60
export POLAROID_MAX_IMAGE_PIXELS=24000000
export POLAROID_RATE_LIMIT_REQUESTS=60
export POLAROID_RATE_LIMIT_WINDOW=60
```

## Execucao com Gunicorn

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
gunicorn --workers 2 --threads 2 --timeout 120 --bind 127.0.0.1:8000 wsgi:application
```

Coloque Nginx na frente, com HTTPS, `client_max_body_size 50m`,
proxy para `127.0.0.1:8000`, e firewall da Oracle liberando apenas 80/443.

## Controles de seguranca aplicados

- senha HTTP Basic obrigatoria quando `POLAROID_PASSWORD` esta definida
- sem uso do nome de arquivo enviado pelo usuario no filesystem
- validacao real de imagem com Pillow
- limite de tamanho total, numero de fotos e quantidade de pixels
- bloqueio de imagens animadas
- rate limit simples por IP/usuario/endpoint
- headers basicos de seguranca
- pagina sem inserir nome de arquivo via HTML cru
