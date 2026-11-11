#!/bin/sh
# Pairs an 8BitDo gamepad with the board. Run it once, on the board:
#     ./pair-gamepad.sh [seconds to look, default 120]
#
# First put the controller in D-input (Android) mode and pairing mode. On the
# SF30 Pro: hold START + B to switch it on, then hold PAIR for 3 s until the
# lights blink quickly. After pairing, switching it on in the same mode connects
# it to the robot again.

SECONDS_TO_LOOK=${1:-120}
echo "Looking for an 8BitDo controller for up to $SECONDS_TO_LOOK s..."
bluetoothctl pairable on >/dev/null
bluetoothctl --timeout "$SECONDS_TO_LOOK" scan on >/dev/null 2>&1 &
SCAN=$!

MAC=""
END=$(( $(date +%s) + SECONDS_TO_LOOK ))
while [ -z "$MAC" ] && [ "$(date +%s)" -lt "$END" ]; do
    sleep 2
    MAC=$(bluetoothctl devices | grep -i -E "8bitdo|sf30" | head -n 1 | cut -d ' ' -f 2)
done
kill "$SCAN" 2>/dev/null
bluetoothctl scan off >/dev/null 2>&1

if [ -z "$MAC" ]; then
    echo "No 8BitDo controller found. Is it in D-input mode and blinking quickly (pairing)?"
    exit 1
fi

echo "Found $(bluetoothctl info "$MAC" | sed -n 's/^[[:space:]]*Name: //p') ($MAC). Pairing..."
bluetoothctl --timeout 30 --agent NoInputNoOutput pair "$MAC" | grep -i -E "success|fail|error"
bluetoothctl trust "$MAC" >/dev/null
bluetoothctl --timeout 15 connect "$MAC" | grep -i -E "success|fail|error"
bluetoothctl info "$MAC" | grep -E "Name|Paired|Bonded|Trusted|Connected"
