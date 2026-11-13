#!/bin/bash
# Installs the RobotRover Bluetooth relay on the UNO Q's Linux side.
# Run on the board:   bash setup.sh
# Needs internet on the board this one time (for apt and pip).
set -euo pipefail

INSTALL_DIR=/opt/robot-ble
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing system packages"
sudo apt-get update
sudo apt-get install -y python3-venv bluez

echo "==> Copying files to $INSTALL_DIR"
sudo mkdir -p "$INSTALL_DIR"
sudo cp "$HERE/robot_ble_bridge.py" "$HERE/robot_gamepad.py" "$HERE/pair-gamepad.sh" "$INSTALL_DIR/"
sudo chmod +x "$INSTALL_DIR/pair-gamepad.sh"

echo "==> Creating Python environment and installing bless + msgpack"
sudo python3 -m venv "$INSTALL_DIR/venv"
sudo "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo "$INSTALL_DIR/venv/bin/pip" install bless==0.3.0 msgpack==1.2.3

echo "==> Turning on Bluetooth"
sudo rfkill unblock bluetooth || true
sudo systemctl enable --now bluetooth
sudo bluetoothctl power on || true

echo "==> Installing and starting the service"
sudo cp "$HERE/robot-ble-bridge.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable robot-ble-bridge
sudo systemctl restart robot-ble-bridge

echo
echo "Done. Check it with:"
echo "  sudo $INSTALL_DIR/venv/bin/python $INSTALL_DIR/robot_ble_bridge.py --send pos"
echo "  systemctl status robot-ble-bridge"
echo "  journalctl -u robot-ble-bridge -f"
