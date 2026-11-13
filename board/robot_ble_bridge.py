#!/usr/bin/env python3
"""
RobotRover Bluetooth relay - runs on the Arduino UNO Q's Linux side.

    phone app --Bluetooth LE--> this script --arduino-router--> RobotRover sketch (STM32)
    8BitDo gamepad --Bluetooth Classic--^   (robot_gamepad.py)

The phone writes text commands (like "w 300" or "base 45") to a Bluetooth LE
"Nordic UART Service". This script checks each command against an allowlist,
calls the sketch's "robot" Bridge method with it, and sends the sketch's short
reply back to the phone. A paired gamepad's left stick, D-pad and buttons become
the same commands, through the same queue; while the gamepad is driving, the
phone's drive commands are ignored.

"poweroff" is handled here rather than passed through: the sketch is told to
stop and show a power icon, then Linux shuts down (systemctl halt) so the
battery can be switched off safely. That needs root (the systemd install) or a sudoers rule
for the arduino user (see README).

Test the sketch link without Bluetooth:
    ./run.sh --send pos                                  (offline install, in ~/robot-ble)
    sudo /opt/robot-ble/venv/bin/python /opt/robot-ble/robot_ble_bridge.py --send pos   (setup.sh install)
"""

import argparse
import asyncio
import collections
import logging
import os
import re
import socket
import subprocess
import sys
import threading
import time

import msgpack

DEVICE_NAME = "RobotRover"
ROUTER_SOCKET = "/var/run/arduino-router.sock"
BRIDGE_METHOD = "robot"          # must match Bridge.provide_safe("robot", ...) in the sketch
ROUTER_TIMEOUT_S = 3.0
QUEUE_LIMIT = 50
MAX_REPLY_BYTES = 180            # the app asks for a bigger Bluetooth packet size; keep replies under it
# Halt rather than poweroff: on this board a powered-off system starts again within seconds
# while power is connected, but a halted one stays down for about 45 s, with the
# microcontroller still running to show the "safe to switch off" face. Must match the
# sudoers rule in the README.
POWEROFF_CMD = ["/usr/bin/systemctl", "halt"]

# A Linux-only reboot (or a router restart) leaves the microcontroller running but
# registered with the old router, so "robot" is "not available" until the sketch
# restarts. Arduino's script pulses the STM32's reset line through GPIO (the arduino
# user is in the gpiod group, so no sudo is needed).
MCU_RESET_CMD = ["/opt/openocd/bin/arduino-reset.sh"]
SKETCH_WAIT_S = 20               # at startup, give a sketch that doesn't answer at all this long first
UNREGISTERED_RESET_S = 5         # ...but reset sooner if the router keeps saying "not available"
MCU_RESET_EVERY_S = 30           # never reset more often than this

# Nordic UART Service - a common, well-supported way to send text over Bluetooth LE
NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # phone writes commands here
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # we send replies here (notify)

# Only these commands are passed to the robot. Anything else is rejected.
ALLOWED = re.compile(
    r"^(?:(?:w|a|s|d) \d{1,5}|w|a|s|d|x|stop|open|close|home|pos|batt|poweroff"
    r"|(?:speed|base|shoulder|elbow|grip) \d{1,3}|m -?\d{1,3} -?\d{1,3}(?: \d{1,5})?)$",
    re.ASCII,   # plain 0-9 only
)

# Drive commands (list every one here). While the gamepad is driving, the phone's are
# ignored until PAD_DRIVE_HOLD_S after the gamepad's last one. Stop always works.
DRIVE_CMD = re.compile(r"^(?:w|a|s|d|m)(?: |$)")
STOP_CMD = re.compile(r"^(?:x|stop)$")
PAD_DRIVE_HOLD_S = 0.5

# After the gamepad changes the arm or the speed, the phone is sent one "pos" line once the
# gamepad has been quiet this long, so the app's sliders follow without flooding its log.
PAD_SYNC_QUIET_S = 0.5
PAD_CHANGES = re.compile(r"^(?:speed|base|shoulder|elbow|grip|open|close|home)(?: |$)")

log = logging.getLogger("robot-ble")


class RouterClient:
    """Minimal MessagePack-RPC client for arduino-router's Unix socket."""

    def __init__(self, path):
        self.path = path
        self.sock = None
        self.unpacker = None
        self.msgid = 0
        self.lock = threading.Lock()

    def _connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(ROUTER_TIMEOUT_S)
        s.connect(self.path)
        self.sock = s
        self.unpacker = msgpack.Unpacker(raw=False)

    def _close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.unpacker = None

    def call(self, method, *params):
        """Call a method on the router (for us: the sketch) and return its result."""
        with self.lock:
            for attempt in (1, 2):
                try:
                    if self.sock is None:
                        self._connect()
                    self.msgid = (self.msgid + 1) & 0x7FFFFFFF
                    msgid = self.msgid
                    # MessagePack-RPC request: [type=0, msgid, method, params]
                    self.sock.sendall(msgpack.packb([0, msgid, method, list(params)]))
                    return self._wait_for_response(msgid, method)
                except socket.timeout:
                    self._close()
                    raise TimeoutError(f"no answer from '{method}' (is the sketch running?)")
                except (ConnectionError, OSError):
                    # Router restarted or socket went stale: reconnect once, then give up
                    self._close()
                    if attempt == 2:
                        raise

    def _wait_for_response(self, msgid, method):
        while True:
            for msg in self.unpacker:
                # MessagePack-RPC response: [type=1, msgid, error, result]
                if isinstance(msg, (list, tuple)) and len(msg) == 4 and msg[0] == 1 and msg[1] == msgid:
                    error, result = msg[2], msg[3]
                    if error:
                        raise RuntimeError(f"'{method}' failed: {error}")
                    return result
                # Anything else (other ids, notifications) is not for us; skip it
            data = self.sock.recv(4096)
            if not data:
                raise ConnectionError("router closed the connection")
            self.unpacker.feed(data)


def sketch_state(router):
    """"ok", "unregistered" (the router is up but has no "robot" method) or "down"."""
    try:
        router.call(BRIDGE_METHOD, "pos")
        return "ok"
    except Exception as exc:
        return "unregistered" if "not available" in str(exc) else "down"


def wait_for_sketch(router, seconds, unregistered_limit=None):
    """True once the sketch answers. Gives up after `seconds`, or sooner if the router has
    said "not available" for `unregistered_limit` seconds in a row."""
    deadline = time.monotonic() + seconds
    unregistered_since = None
    while time.monotonic() < deadline:
        state = sketch_state(router)
        if state == "ok":
            return True
        if state != "unregistered":
            unregistered_since = None
        elif unregistered_since is None:
            unregistered_since = time.monotonic()
        elif unregistered_limit is not None and time.monotonic() - unregistered_since >= unregistered_limit:
            return False
        time.sleep(1)
    return False


_last_reset = float("-inf")
_reset_lock = threading.Lock()


def reset_mcu(router):
    """Restart the sketch so it registers with the router again. Returns True if it answers."""
    global _last_reset
    with _reset_lock:
        if time.monotonic() - _last_reset < MCU_RESET_EVERY_S:
            return False
        _last_reset = time.monotonic()
        log.warning("sketch not registered with the router; resetting the microcontroller")
        try:
            subprocess.run(MCU_RESET_CMD, capture_output=True, timeout=30, check=True)
        except Exception as exc:
            log.warning("microcontroller reset failed: %s", exc)
            return False
    ok = wait_for_sketch(router, 15)
    log.info("sketch is back" if ok else "sketch still not answering after the reset")
    return ok


def ensure_sketch(router):
    """At startup: wait for the sketch, and reset the microcontroller once if it never answers."""
    if wait_for_sketch(router, SKETCH_WAIT_S, UNREGISTERED_RESET_S):
        log.info("sketch is answering")
    else:
        reset_mcu(router)


async def power_off(router, notify):
    """Stop the robot, then shut Linux down so the battery can be switched off."""
    try:
        # The sketch stops the wheels, refuses moves and shows a power icon
        await asyncio.to_thread(router.call, BRIDGE_METHOD, "poweroff")
    except Exception as exc:
        log.warning("sketch did not take poweroff: %s", exc)   # shut down anyway
    notify("powering off: switch off when the face sleeps")

    # sudo -n fails at once instead of waiting for a password nobody can type
    cmd = POWEROFF_CMD if os.geteuid() == 0 else ["sudo", "-n", *POWEROFF_CMD]
    try:
        result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=15)
        ok, why = result.returncode == 0, (result.stderr or result.stdout).strip()
    except Exception as exc:
        ok, why = False, str(exc)
    if ok:
        log.info("powering off")
        return

    log.warning("poweroff failed: %s", why)
    if "password" in why:
        notify("poweroff not allowed: add the sudoers rule (see README)")
    else:
        notify(f"poweroff failed: {why[:60]}")
    try:
        await asyncio.to_thread(router.call, BRIDGE_METHOD, "poweroff 0")   # back to normal
    except Exception:
        pass


async def run_ble(router, use_gamepad=True):
    # Imported here so "--send" testing works even before bless is installed
    from bless import (
        BlessServer,
        GATTAttributePermissions,
        GATTCharacteristicProperties,
    )

    loop = asyncio.get_running_loop()
    queue = collections.deque()      # only touched on the event loop's thread
    queued = asyncio.Event()
    server = BlessServer(name=DEVICE_NAME, loop=loop)

    def notify(text):
        characteristic = server.get_characteristic(NUS_TX)
        if characteristic is None:
            return
        characteristic.value = bytearray(text.encode("utf-8")[:MAX_REPLY_BYTES])
        server.update_value(NUS_SERVICE, NUS_TX)

    # Queue items: (source "phone" or "pad", command line)
    def enqueue(item):
        source, line = item
        if DRIVE_CMD.match(line) or STOP_CMD.match(line):
            # A newer drive or stop command replaces this source's older drive commands that
            # haven't run yet, so a backlog (sketch slow to answer) can't replay stale driving
            for old in [q for q in queue if q[0] == source and DRIVE_CMD.match(q[1])]:
                queue.remove(old)
        if len(queue) >= QUEUE_LIMIT:
            log.warning("queue full, dropped %r", queue.popleft()[1])
        queue.append(item)
        queued.set()

    def on_read(characteristic, **kwargs):
        return characteristic.value

    def on_write(characteristic, value, **kwargs):
        if str(characteristic.uuid).lower() != NUS_RX:
            return
        text = bytes(value).decode("utf-8", errors="replace")
        # One write may hold several commands separated by newlines
        for line in text.replace("\r", "\n").split("\n"):
            line = " ".join(line.strip().lower().split())
            if line:
                loop.call_soon_threadsafe(enqueue, ("phone", line))

    # Called from the gamepad thread
    def pad_send(line):
        loop.call_soon_threadsafe(enqueue, ("pad", line))

    pad_drive_until = 0.0
    pad_on_reply = None      # set when gamepad support starts
    pad_sync = None          # pending timer for the phone's "pos" line

    async def worker():
        nonlocal pad_drive_until, pad_sync
        while True:
            while not queue:
                queued.clear()
                await queued.wait()
            source, line = queue.popleft()
            from_phone = source != "pad"     # "phone", or "sync": a pos line for the phone
            if not ALLOWED.match(line):
                log.warning("rejected %r from the %s", line, source)
                if from_phone:
                    notify(f"rejected: {line[:40]}")
                continue
            if DRIVE_CMD.match(line):
                if not from_phone:
                    pad_drive_until = time.monotonic() + PAD_DRIVE_HOLD_S
                elif time.monotonic() < pad_drive_until:
                    log.debug("ignored %r from the phone: the gamepad is driving", line)
                    continue
            if line == "poweroff":
                await power_off(router, notify)
                continue
            try:
                reply = str(await asyncio.to_thread(router.call, BRIDGE_METHOD, line))
                log.debug("%s %s -> %s", source, line, reply)
                if from_phone:
                    notify(reply)      # the gamepad's replies would flood the phone's log
                elif PAD_CHANGES.match(line):
                    if pad_sync:
                        pad_sync.cancel()
                    pad_sync = loop.call_later(PAD_SYNC_QUIET_S, enqueue, ("sync", "pos"))
                if pad_on_reply:
                    pad_on_reply(reply)   # the gamepad tracks angles and speed whoever changed them
            except Exception as exc:  # keep running no matter what
                log.warning("%s failed: %s", line, exc)
                if "not available" in str(exc):
                    if from_phone:
                        notify("robot restarting, try again in a few seconds")
                    threading.Thread(target=reset_mcu, args=(router,), daemon=True).start()
                elif from_phone:
                    notify(f"error: {exc}")

    server.read_request_func = on_read
    server.write_request_func = on_write

    await server.add_new_service(NUS_SERVICE)
    await server.add_new_characteristic(
        NUS_SERVICE,
        NUS_RX,
        GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response,
        bytearray(),
        GATTAttributePermissions.writeable,
    )
    await server.add_new_characteristic(
        NUS_SERVICE,
        NUS_TX,
        GATTCharacteristicProperties.read | GATTCharacteristicProperties.notify,
        bytearray(),
        GATTAttributePermissions.readable,
    )

    worker_task = asyncio.create_task(worker())
    await server.start()
    log.info("Advertising as '%s'. Waiting for the phone...", DEVICE_NAME)

    if use_gamepad:
        try:
            from robot_gamepad import GamepadReader
            reader = GamepadReader(pad_send)
            pad_on_reply = reader.logic.on_reply
            reader.start()
            log.info("Watching for a paired gamepad")
        except Exception as exc:   # the phone keeps working even if this fails
            log.warning("gamepad support not started: %s", exc)

    try:
        await asyncio.Event().wait()   # run forever
    finally:
        worker_task.cancel()
        await server.stop()


def main():
    parser = argparse.ArgumentParser(description="RobotRover Bluetooth LE relay")
    parser.add_argument("--send", metavar="CMD", help="send one command to the sketch and print the reply, then exit")
    parser.add_argument("--socket", default=ROUTER_SOCKET, help=f"arduino-router socket (default {ROUTER_SOCKET})")
    parser.add_argument("--verbose", action="store_true", help="log every command")
    parser.add_argument("--reset-mcu", action="store_true", help="restart the sketch (reset the microcontroller), then exit")
    parser.add_argument("--gamepad-test", action="store_true", help="print the gamepad's buttons and sticks as they change")
    parser.add_argument("--no-gamepad", action="store_true", help="don't use a paired gamepad")
    args = parser.parse_args()

    if args.gamepad_test:
        from robot_gamepad import test
        sys.exit(test())

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    router = RouterClient(args.socket)

    if args.send:
        if " ".join(args.send.lower().split()) == "poweroff":
            # The real thing, as from the app: tell the sketch, then shut Linux down
            asyncio.run(power_off(router, print))
            return
        try:
            print(router.call(BRIDGE_METHOD, args.send))
        except Exception as exc:
            print(f"Failed: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    if args.reset_mcu:
        print("sketch is back" if reset_mcu(router) else "sketch did not answer after the reset")
        return

    # Check the sketch in the background so Bluetooth starts advertising right away
    threading.Thread(target=ensure_sketch, args=(router,), daemon=True).start()
    try:
        asyncio.run(run_ble(router, use_gamepad=not args.no_gamepad))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
