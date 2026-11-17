#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'با sudo اجرا کن.'; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
APP=/opt/rustdeskpanel; DATA=/var/lib/rustdeskpanel; CFG=/etc/rustdeskpanel
SERVER_IP=${PANEL_BIND:-172.16.2.99}; PORT=${PANEL_PORT:-8765}
command -v python3 >/dev/null; command -v openssl >/dev/null; command -v curl >/dev/null
if ! id rustdeskpanel >/dev/null 2>&1; then useradd --system --user-group --no-create-home --shell /usr/sbin/nologin rustdeskpanel; fi
getent group mizyar-web >/dev/null 2>&1 || groupadd --system mizyar-web
if id mizyar-web >/dev/null 2>&1; then usermod -aG mizyar-web rustdeskpanel; fi
systemctl disable --now mizyar-panel.service 2>/dev/null || true
install -d -o root -g rustdeskpanel -m 0750 "$APP"
install -d -o rustdeskpanel -g rustdeskpanel -m 0750 "$DATA" "$DATA/backups"
install -d -o root -g rustdeskpanel -m 0750 "$CFG"

install -o root -g rustdeskpanel -m 0640 "$SRC/server.py" "$APP/server.py"
install -o root -g rustdeskpanel -m 0640 "$SRC/index.html" "$APP/index.html"
install -o root -g rustdeskpanel -m 0640 "$SRC/VERSION" "$APP/VERSION"
install -o root -g root -m 0755 "$SRC/update-root.sh" /usr/local/sbin/rustdeskpanel-update
install -o root -g root -m 0755 "$SRC/launch-update.sh" /usr/local/sbin/rustdeskpanel-launch-update
ADMIN_PASSWORD=$(openssl rand -hex 10); DEVICE_KEY=$(openssl rand -hex 32)
cat > "$CFG/panel.env" <<EOF
PANEL_BIND=$SERVER_IP
PANEL_PORT=$PORT
PANEL_DATA=$DATA
PANEL_STATUS_FILE=/var/lib/mizyar-panel/status.json
PANEL_CERT=$CFG/tls.crt
PANEL_KEY=$CFG/tls.key
PANEL_ADMIN_PASSWORD=$ADMIN_PASSWORD
PANEL_DEVICE_KEY=$DEVICE_KEY
EOF
chmod 0600 "$CFG/panel.env"
openssl req -x509 -newkey rsa:2048 -nodes -days 825 -keyout "$CFG/tls.key" -out "$CFG/tls.crt" -subj "/CN=$SERVER_IP" -addext "subjectAltName=IP:$SERVER_IP" >/dev/null 2>&1
chmod 0640 "$CFG/tls.key"; chown root:rustdeskpanel "$CFG/tls.key"; chmod 0644 "$CFG/tls.crt"
cat >/etc/systemd/system/rustdeskpanel.service <<EOF
[Unit]
Description=RustDesk Panel
After=network-online.target docker.service
Wants=network-online.target
[Service]
Type=simple
User=rustdeskpanel
Group=rustdeskpanel
SupplementaryGroups=mizyar-web
EnvironmentFile=$CFG/panel.env
WorkingDirectory=$APP
ExecStart=/usr/bin/python3 $APP/server.py
Restart=on-failure
RestartSec=3
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadOnlyPaths=$APP $CFG
ReadWritePaths=$DATA
[Install]
WantedBy=multi-user.target
EOF
printf '%s\n' 'rustdeskpanel ALL=(root) NOPASSWD: /usr/local/sbin/rustdeskpanel-launch-update' > /etc/sudoers.d/rustdeskpanel-update
chmod 0440 /etc/sudoers.d/rustdeskpanel-update
visudo -cf /etc/sudoers.d/rustdeskpanel-update >/dev/null
cat >/root/rustdeskpanel-login.txt <<EOF
URL: https://$SERVER_IP:$PORT
Username: admin
Password: $ADMIN_PASSWORD
Device-Agent-Key: $DEVICE_KEY
EOF
chmod 0600 /root/rustdeskpanel-login.txt
systemctl daemon-reload
systemctl enable --now rustdeskpanel.service
echo "پنل نصب شد: https://$SERVER_IP:$PORT"
echo 'حساب ورود و کلید Agent در /root/rustdeskpanel-login.txt ذخیره شد.'
echo 'برای دریافت گزارش کانتینرها، collector نسخهٔ قبلی باید فعال بماند.'
