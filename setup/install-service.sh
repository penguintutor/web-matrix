#!/bin/bash
set -e

# Ensure the script is run with sudo from a normal user account
if [ "$EUID" -ne 0 ] || [ -z "$SUDO_USER" ]; then
    echo "Please run this script using sudo from your normal user account:"
    echo "  sudo $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_TEMPLATE="$SCRIPT_DIR/matrix-daemon.service"
TARGET_SERVICE="/etc/systemd/system/matrix-daemon.service"

if [ ! -f "$SERVICE_TEMPLATE" ]; then
    echo "Error: Could not find $SERVICE_TEMPLATE"
    exit 1
fi

echo "Installing matrix-daemon.service for user: $SUDO_USER..."

# Replace <username> with the actual user and write to systemd directory
sed "s/<username>/$SUDO_USER/g" "$SERVICE_TEMPLATE" > "$TARGET_SERVICE"
chmod 644 "$TARGET_SERVICE"

# Reload systemd, enable on boot, and start immediately
systemctl daemon-reload
systemctl enable --now matrix-daemon.service

echo "Done! Checking service status:"
systemctl status matrix-daemon.service --no-pager
