#!/bin/sh
# Keeps the RobotRover Bluetooth relay running; restarts it if it stops.
# Started at boot from the arduino user crontab (crontab -l to see it).
cd "$(dirname "$0")"
sleep 10   # let Bluetooth and the Arduino router finish starting
while true; do
  echo "--- relay starting $(date)" >> relay.log
  ./run.sh >> relay.log 2>&1
  sleep 3
done
