#!/usr/bin/env bash
set -uo pipefail

NAME=docker-notify
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

[ "$(id -u)" -ne 0 ] || { echo "error: run as your normal user, not root" >&2; exit 1; }

systemctl --user disable --now "$NAME.timer" 2>/dev/null
systemctl --user stop "$NAME.service" 2>/dev/null
rm -f "$CONF_HOME/systemd/user/$NAME.service" "$CONF_HOME/systemd/user/$NAME.timer"
rm -rf "$CONF_HOME/$NAME" "$REPO/system"
systemctl --user daemon-reload
systemctl --user reset-failed 2>/dev/null

echo "Removed timer, service, config and generated files. The repo itself is untouched."