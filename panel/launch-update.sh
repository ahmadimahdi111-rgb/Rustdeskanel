#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/systemd-run --quiet --collect --unit=rustdeskpanel-update --description="RustDesk Panel Online Update" /usr/local/sbin/rustdeskpanel-update
