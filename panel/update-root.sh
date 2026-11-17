#!/usr/bin/env bash
set -euo pipefail
APP=/opt/rustdeskpanel
DATA=/var/lib/rustdeskpanel
REPO=ahmadimahdi111-rgb/Rustdeskanel
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DATA/backups"
if [[ -f "$DATA/panel.sqlite3" ]]; then python3 - "$DATA/panel.sqlite3" "$DATA/backups/pre-update-$(date +%Y%m%d-%H%M%S).sqlite3" <<'PY'
import sqlite3,sys
src=sqlite3.connect(sys.argv[1]); dst=sqlite3.connect(sys.argv[2]); src.backup(dst); dst.close(); src.close()
PY
fi
curl -fL --retry 2 "https://codeload.github.com/$REPO/tar.gz/refs/heads/main" -o "$TMP/source.tar.gz"
tar -xzf "$TMP/source.tar.gz" -C "$TMP"
SRC=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -n1)/panel
test -f "$SRC/server.py" && test -f "$SRC/index.html" && test -f "$SRC/VERSION"
install -d -o root -g rustdeskpanel -m 0750 "$APP"
install -o root -g rustdeskpanel -m 0640 "$SRC/server.py" "$APP/server.py"
install -o root -g rustdeskpanel -m 0640 "$SRC/index.html" "$APP/index.html"
install -o root -g rustdeskpanel -m 0640 "$SRC/VERSION" "$APP/VERSION"
install -o root -g root -m 0755 "$SRC/update-root.sh" /usr/local/sbin/rustdeskpanel-update
systemctl restart rustdeskpanel.service
echo "به‌روزرسانی به نسخه $(cat "$APP/VERSION") انجام شد."
