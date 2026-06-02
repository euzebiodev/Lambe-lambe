#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Informe o diretorio do workspace do AlbumPolaroid."
    exit 2
fi

WORKSPACE="$(readlink -f "$1")"

case "$WORKSPACE" in
    /var/lib/jenkins/jobs/album-polaroid-cd/workspace|/home/euzebio/Projetos/Repositorios/AlbumPolaroid|/home/euzebio/Projetos/Repositorios/Lambe-lambe)
        ;;
    *)
        echo "Workspace nao permitido: $WORKSPACE"
        exit 2
        ;;
esac

if [ ! -f "$WORKSPACE/wsgi.py" ] || [ ! -f "$WORKSPACE/requirements-service.txt" ]; then
    echo "Workspace invalido: $WORKSPACE"
    exit 2
fi

SERVICE_USER="album-polaroid"
APP_DIR="/opt/album-polaroid"
RELEASE_DIR="$APP_DIR/app"
VENV_DIR="$APP_DIR/venv"
CONFIG_DIR="/etc/album-polaroid"
ENV_FILE="$CONFIG_DIR/album-polaroid.env"
TMP_RELEASE="$(mktemp -d)"

cleanup() {
    rm -rf "$TMP_RELEASE"
}
trap cleanup EXIT

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -o root -g root -m 0755 "$APP_DIR"
install -d -o root -g root -m 0755 "$CONFIG_DIR"

if [ ! -f "$ENV_FILE" ]; then
    PASSWORD="$(openssl rand -base64 24)"
    cat > "$ENV_FILE" <<EOF
POLAROID_PASSWORD=$PASSWORD
POLAROID_MAX_UPLOAD_MB=50
POLAROID_MAX_FILES=60
POLAROID_MAX_IMAGE_PIXELS=24000000
POLAROID_RATE_LIMIT_REQUESTS=60
POLAROID_RATE_LIMIT_WINDOW=60
EOF
    chown root:"$SERVICE_USER" "$ENV_FILE"
    chmod 0640 "$ENV_FILE"
fi

tar \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='build' \
    --exclude='dist' \
    --exclude='installer-output' \
    -C "$WORKSPACE" \
    -cf - . | tar -C "$TMP_RELEASE" -xf -

rm -rf "$RELEASE_DIR"
install -d -o root -g root -m 0755 "$RELEASE_DIR"
cp -a "$TMP_RELEASE/." "$RELEASE_DIR/"
chown -R root:root "$RELEASE_DIR"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
"$VENV_DIR/bin/python" -m pip install -r "$RELEASE_DIR/requirements-service.txt"
chown -R root:root "$VENV_DIR"

cat > /etc/systemd/system/album-polaroid.service <<EOF
[Unit]
Description=AlbumPolaroid Lambe-lambe web service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$RELEASE_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$VENV_DIR/bin/gunicorn --workers 2 --threads 2 --timeout 120 --bind 0.0.0.0:8091 wsgi:application
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadOnlyPaths=$RELEASE_DIR $VENV_DIR
ReadWritePaths=/tmp

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable album-polaroid.service
systemctl restart album-polaroid.service

for attempt in $(seq 1 24); do
    if systemctl is-active --quiet album-polaroid.service && curl -fsS -u "admin:$(sed -n 's/^POLAROID_PASSWORD=//p' "$ENV_FILE")" http://127.0.0.1:8091/ >/dev/null; then
        echo "album-polaroid UP"
        exit 0
    fi
    sleep 5
done

systemctl status album-polaroid.service --no-pager -l
exit 1
