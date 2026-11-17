#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'با sudo اجرا کن.'; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
APP=/opt/rustdeskpanel; DATA=/var/lib/rustdeskpanel; CFG=/etc/rustdeskpanel
id rustdeskpanel >/dev/null 2>&1 || { echo 'سرویس نصب نیست؛ ابتدا install.sh را اجرا کن.'; exit 1; }
test -f "$SRC/server.py" && test -f "$SRC/index.html" && test -f "$SRC/VERSION"
install -d -o root -g rustdeskpanel -m 0750 "$APP"
install -d -o rustdeskpanel -g rustdeskpanel -m 0750 "$DATA" "$DATA/backups"
install -d -o root -g rustdeskpanel -m 0750 "$CFG"
install -o root -g rustdeskpanel -m 0640 "$SRC/server.py" "$APP/server.py"
install -o root -g rustdeskpanel -m 0640 "$SRC/index.html" "$APP/index.html"
install -o root -g rustdeskpanel -m 0640 "$SRC/VERSION" "$APP/VERSION"
install -o root -g root -m 0755 "$SRC/update-root.sh" /usr/local/sbin/rustdeskpanel-update
chown rustdeskpanel:rustdeskpanel "$DATA"
chmod 0750 "$DATA"
if [[ -f "$CFG/tls.key" ]]; then chown root:rustdeskpanel "$CFG/tls.key"; chmod 0640 "$CFG/tls.key"; fi
if [[ -f "$CFG/tls.crt" ]]; then chmod 0644 "$CFG/tls.crt"; fi
systemctl restart rustdeskpanel.service
echo "به‌روزرسانی به نسخه $(cat "$APP/VERSION") انجام شد؛ اطلاعات ورود، پایگاه‌داده و گواهی حفظ شدند."
