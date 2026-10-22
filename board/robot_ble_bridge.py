#!/usr/bin/env python3
"""
RobotRover Bluetooth relay - runs on the Arduino UNO Q's Linux side.

    phone app --Bluetooth LE--> this script --arduino-router--> RobotRover sketch (STM32)

The phone writes text commands (like "w 300" or "base 45") to a Bluetooth LE
"Nordic UART Service". This script checks each command against an allowlist,
calls the sketch's "robot" Bridge method with it, and sends the sketch's short
reply back to the phone.

Test the sketch link without Bluetooth:
    sudo /opt/robot-ble/venv/bin/python /opt/robot-ble/robot_ble_bridge.py --send pos
"""

import argparse
import asyncio
import logging
import re
import socket
import sys
import threading

import msgpack

DEVICE_NAME = "RobotRover"
ROUTER_SOCKET = "/var/run/arduino-router.sock"
BRIDGE_METHOD = "robot"          # must match Bridge.provide_safe("robot", ...) in the sketch
ROUTER_TIMEOUT_S = 3.0
QUEUE_LIMIT = 50
MAX_REPLY_BYTES = 180            # the app asks for a bigger Bluetooth packet size; keep replies under it

# Nordic UART Service - a common, well-supported way to send text over Bluetooth LE
NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"   # phone writes commands here
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"   # we send replies here (notify)

# Only these commands are passed to the robot. Anything else is rejected.
ALLOWED = re.compile(
    r"^(?:(?:w|a|s|d) \d{1,5}|w|a|s|d|x|stop|open|close|home|pos"
    r"|(?:speed|base|shoulder|elbow|grip) \d{1,3})$"
)

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


async def run_ble(router):
    # Imported here so "--send" testing works even before bless is installed
    from bless import (
        BlessServer,
        GATTAttributePermissions,
        GATTCharacteristicProperties,
    )

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=QUEUE_LIMIT)
    server = BlessServer(name=DEVICE_NAME, loop=loop)

    def notify(text):
        characteristic = server.get_characteristic(NUS_TX)
        if characteristic is None:
            return
        characteristic.value = bytearray(text.encode("utf-8")[:MAX_REPLY_BYTES])
        server.update_value(NUS_SERVICE, NUS_TX)

    def enqueue(line):
        if queue.full():
            dropped = queue.get_nowait()
            log.warning("queue full, dropped %r", dropped)
        queue.put_nowait(line)

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
                loop.call_soon_threadsafe(enqueue, line)

    async def worker():
        while True:
            line = await queue.get()
            if not ALLOWED.match(line):
                log.warning("rejected %r", line)
                notify(f"rejected: {line[:40]}")
                continue
            try:
                reply = await asyncio.to_thread(router.call, BRIDGE_METHOD, line)
                log.debug("%s -> %s", line, reply)
                notify(str(reply))
            except Exception as exc:  # keep running no matter what
                log.warning("%s failed: %s", line, exc)
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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    router = RouterClient(args.socket)

    if args.send:
        try:
            print(router.call(BRIDGE_METHOD, args.send))
        except Exception as exc:
            print(f"Failed: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        asyncio.run(run_ble(router))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
