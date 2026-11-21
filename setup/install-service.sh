#!/bin/bash
set -e

# Ensure the script is run with sudo from a normal user account
if [ "$EUID" -ne 0 ] || [ -z "$SUDO_USER" ]; then
    echo "Please run this script using sudo from your normal user account:"
    echo "  sudo $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
SERVICE_TEMPLATE="$SCRIPT_DIR/matrix-daemon.service"
TARGET_SERVICE="/etc/systemd/system/matrix-daemon.service"
BLACKLIST_FILE="/etc/modprobe.d/blacklist-rgb-matrix.conf"
REBOOT_REQUIRED=0

if [ ! -f "$SERVICE_TEMPLATE" ]; then
    echo "Error: Could not find $SERVICE_TEMPLATE"
    exit 1
fi

# 1. Disable onboard audio (conflicts with rpi-rgb-led-matrix hardware PWM)
CONFIG_FILE=""
if [ -f "/boot/firmware/config.txt" ]; then
    CONFIG_FILE="/boot/firmware/config.txt"
elif [ -f "/boot/config.txt" ]; then
    CONFIG_FILE="/boot/config.txt"
fi

if [ -n "$CONFIG_FILE" ]; then
    if grep -q "^dtparam=audio=on" "$CONFIG_FILE"; then
        echo "Disabling onboard audio in $CONFIG_FILE..."
        sed -i 's/^dtparam=audio=on/#dtparam=audio=on/' "$CONFIG_FILE"
        REBOOT_REQUIRED=1
    fi
    if ! grep -q "^dtparam=audio=off" "$CONFIG_FILE"; then
        echo "Adding dtparam=audio=off to $CONFIG_FILE..."
        echo "dtparam=audio=off" >> "$CONFIG_FILE"
        REBOOT_REQUIRED=1
    fi
fi

if [ ! -f "$BLACKLIST_FILE" ] || ! grep -q "blacklist snd_bcm2835" "$BLACKLIST_FILE"; then
    echo "Blacklisting snd_bcm2835 in $BLACKLIST_FILE..."
    echo "blacklist snd_bcm2835" > "$BLACKLIST_FILE"
    REBOOT_REQUIRED=1
fi

if lsmod | grep -q "^snd_bcm2835"; then
    REBOOT_REQUIRED=1
fi

# 2. Configure directory permissions for the daemon user
echo "Configuring permissions for daemon user..."
if [ -n "$USER_HOME" ] && [ -d "$USER_HOME" ]; then
    chmod o+x "$USER_HOME"
fi

for DIR in "$PROJECT_DIR/instance" "$PROJECT_DIR/data" "$PROJECT_DIR/uploads" "$PROJECT_DIR/fonts"; do
    mkdir -p "$DIR"
    chown -R "$SUDO_USER:daemon" "$DIR"
    chmod -R 2775 "$DIR"
done

# 3. Install and enable the systemd service
echo "Installing matrix-daemon.service for user: $SUDO_USER..."
sed "s/<username>/$SUDO_USER/g" "$SERVICE_TEMPLATE" > "$TARGET_SERVICE"
chmod 644 "$TARGET_SERVICE"

systemctl daemon-reload
systemctl enable matrix-daemon.service

# 4. Start immediately or prompt for reboot if audio module is still active
if [ "$REBOOT_REQUIRED" -eq 1 ]; then
    echo ""
    echo "================================================================="
    echo "Service enabled, but a REBOOT is required to unload snd_bcm2835."
    echo "Run 'sudo reboot' now — the daemon will start automatically."
    echo "================================================================="
else
    systemctl restart matrix-daemon.service
    echo "Done! Checking service status:"
    systemctl status matrix-daemon.service --no-pager
fi
