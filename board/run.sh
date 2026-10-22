#!/bin/sh
# Runs the RobotRover Bluetooth relay with its bundled libraries (no install needed).
cd "$(dirname "$0")"
export PYTHONPATH="$PWD/lib"
exec python3 robot_ble_bridge.py "$@"
