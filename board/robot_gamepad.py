#!/usr/bin/env python3
"""
8BitDo SF30 Pro gamepad support for the RobotRover relay (UNO Q, Linux side).

The controller pairs with the board over Bluetooth Classic (board/pair-gamepad.sh)
and shows up as /dev/input/eventN. GamepadReader reads it with plain Python, no
extra packages, and PadLogic turns sticks and buttons into ordinary robot
commands. The relay runs those exactly like the phone's, through the same queue.

    Left stick            drive: up/down is speed, left/right steers, diagonals curve
    D-pad left/right      base           D-pad up/down   shoulder
    L2 / R2               elbow down / up
    A / B                 gripper open / close
    L / R                 top speed down / up
    X                     show the battery on the matrix
    Select                stop
    Start                 home
    Hold Start + Select   power off (3 s)

Check what your controller sends:   ./run.sh --gamepad-test
"""

import glob
import logging
import math
import os
import re
import select
import struct
import threading
import time

log = logging.getLogger("robot-ble")

DEVICE_NAME = re.compile(r"8bitdo|sf30", re.I)   # input devices treated as the robot's controller

# ---- Linux input codes (linux/input-event-codes.h)
EV_KEY, EV_ABS = 0x01, 0x03
ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
ABS_GAS, ABS_BRAKE, ABS_HAT0X, ABS_HAT0Y = 0x09, 0x0A, 0x10, 0x11
BTN_SOUTH = 0x130
ABS_NAMES = {ABS_X: "ABS_X", ABS_Y: "ABS_Y", ABS_Z: "ABS_Z", ABS_RX: "ABS_RX", ABS_RY: "ABS_RY",
             ABS_RZ: "ABS_RZ", ABS_GAS: "ABS_GAS", ABS_BRAKE: "ABS_BRAKE",
             ABS_HAT0X: "ABS_HAT0X", ABS_HAT0Y: "ABS_HAT0Y"}
KEY_NAMES = {0x130: "BTN_SOUTH", 0x131: "BTN_EAST", 0x132: "BTN_C", 0x133: "BTN_NORTH",
             0x134: "BTN_WEST", 0x135: "BTN_Z", 0x136: "BTN_TL", 0x137: "BTN_TR", 0x138: "BTN_TL2",
             0x139: "BTN_TR2", 0x13A: "BTN_SELECT", 0x13B: "BTN_START", 0x13C: "BTN_MODE",
             0x13D: "BTN_THUMBL", 0x13E: "BTN_THUMBR"}

# ---- Map for the SF30 Pro in D-input (Android) mode. Check yours with --gamepad-test.
# Buttons, by the label printed on the controller
BUTTONS = {0x130: "A", 0x131: "B", 0x133: "X", 0x134: "Y", 0x136: "L", 0x137: "R",
           0x138: "L2", 0x139: "R2", 0x13A: "SELECT", 0x13B: "START"}
TRIGGER_AXES = {ABS_BRAKE: "L2", ABS_GAS: "R2"}   # some modes report L2 / R2 as axes instead
LEFT_X, LEFT_Y = ABS_X, ABS_Y   # left stick
RIGHT_Y = (ABS_RZ, ABS_RY)      # right stick up/down (the first one the controller has; tank style only)
DPAD_X, DPAD_Y = ABS_HAT0X, ABS_HAT0Y

# "one-stick": the left stick drives (up/down speed, left/right steering).
# "tank": the left stick's up/down drives the left wheel, the right stick's the right wheel.
DRIVE_STYLE = "one-stick"

# ---- Feel
DEADZONE = 0.15          # ignore small stick movements around the center
PULSE_MS = 400           # each drive command lasts this long on the robot...
REPEAT_S = 0.15          # ...and is repeated this often while a stick is pushed
CHANGE = 20              # or sooner, if a wheel's speed changed by more than this
ARM_STEP_DEG = 4         # an arm joint moves this many degrees...
ARM_STEP_S = 0.08        # ...this often while its button is held (50 degrees a second)
SPEED_STEP = 25          # L / R change the top speed by this much
POWEROFF_HOLD_S = 3.0    # hold Start + Select this long to power off
HOME_TAP_S = 1.0         # Start released sooner than this (and not part of the hold) = home

EVENT = struct.Struct("qqHHi")   # struct input_event on 64-bit Linux: time, type, code, value


class PadLogic:
    """Turns controller state into robot commands. send(line, on_reply) queues one command."""

    def __init__(self, send):
        self.send = send
        self.lock = threading.Lock()
        self.angles = {"base": 90, "shoulder": 90, "elbow": 90}
        self.speed = 180                 # top speed, kept in step with the sketch's "speed"
        self._reset(set())

    def _reset(self, axes):
        self.right_y = next((code for code in RIGHT_Y if code in axes), None)
        if DRIVE_STYLE == "tank":
            self.can_drive = LEFT_Y in axes and self.right_y is not None
        else:
            self.can_drive = LEFT_X in axes and LEFT_Y in axes
        self.axes = {}                   # code -> -1..1
        self.held = {}                   # label -> when it was pressed
        self.driving = False
        self.last_drive = 0.0
        self.last_wheels = (0, 0)
        self.last_arm = 0.0
        self.combo_done = False

    # ---- called by the reader
    def connected(self, axes):
        """axes: the axis codes the controller has. Returns False if it has no sticks to drive with."""
        with self.lock:
            self._reset(axes)
            can_drive = self.can_drive
        self.send("pos", self.on_reply)  # learn the arm angles and the speed
        return can_drive

    def disconnected(self):
        with self.lock:
            was_driving, self.driving = self.driving, False
            self.held.clear()
            self.axes.clear()
        if was_driving:
            self.send("x", None)

    def axis(self, code, value, now):
        with self.lock:
            if code in TRIGGER_AXES:
                self._button(TRIGGER_AXES[code], value > 0.0, now)
            else:
                self.axes[code] = value

    def button(self, label, pressed, now):
        with self.lock:
            self._button(label, pressed, now)

    def on_reply(self, reply):
        """Keeps the arm angles and the top speed in step with what the sketch actually did."""
        with self.lock:
            m = re.match(r"(base|shoulder|elbow) -> (\d+)", reply)
            if m:
                self.angles[m[1]] = int(m[2])
                return
            m = re.match(r"base (\d+) shoulder (\d+) elbow (\d+) gripper \d+ speed (\d+)", reply)
            if m:
                self.angles.update(base=int(m[1]), shoulder=int(m[2]), elbow=int(m[3]))
                self.speed = int(m[4])
                return
            m = re.match(r"speed (\d+)$", reply)
            if m:
                self.speed = int(m[1])

    def tick(self, now):
        with self.lock:
            self._power_off_hold(now)
            self._drive(now)
            if now - self.last_arm >= ARM_STEP_S:
                self.last_arm = now
                self._arm()

    # ---- inside the lock
    def _button(self, label, pressed, now):
        if pressed:
            if label in self.held:
                return                   # already down (or key repeat)
            self.held[label] = now
            if label == "A":
                self.send("open", None)
            elif label == "B":
                self.send("close", None)
            elif label == "X":
                self.send("batt", None)
            elif label == "SELECT":
                self.driving = False
                self.send("x", None)
            elif label in ("L", "R"):
                step = SPEED_STEP if label == "R" else -SPEED_STEP
                self.speed = max(0, min(255, self.speed + step))
                self.send(f"speed {self.speed}", self.on_reply)
        else:
            since = self.held.pop(label, None)
            if since is None:
                return
            if label == "START" and not self.combo_done and now - since < HOME_TAP_S:
                self.send("home", None)
                self.send("pos", self.on_reply)   # home changed the arm angles
            if "START" not in self.held and "SELECT" not in self.held:
                self.combo_done = False

    def _power_off_hold(self, now):
        if self.combo_done or "START" not in self.held or "SELECT" not in self.held:
            return
        if now - max(self.held["START"], self.held["SELECT"]) >= POWEROFF_HOLD_S:
            self.combo_done = True
            self.driving = False
            self.send("poweroff", None)

    @staticmethod
    def _dead(stick):
        """Stick position -1..1 with a dead zone in the middle, rescaled so it still reaches 1."""
        if abs(stick) < DEADZONE:
            return 0.0
        return math.copysign((abs(stick) - DEADZONE) / (1 - DEADZONE), stick)

    def _wheels(self):
        """Left and right wheel speeds from the sticks (sticks report up as negative)."""
        if DRIVE_STYLE == "tank":
            left = self._dead(-self.axes.get(LEFT_Y, 0.0))
            right = self._dead(-self.axes.get(self.right_y, 0.0))
        else:
            throttle = self._dead(-self.axes.get(LEFT_Y, 0.0))
            turn = self._dead(self.axes.get(LEFT_X, 0.0))
            left, right = throttle + turn, throttle - turn
            biggest = max(1.0, abs(left), abs(right))   # full up + full right: left wheel full, right stopped
            left, right = left / biggest, right / biggest
        return int(round(left * self.speed)), int(round(right * self.speed))

    def _drive(self, now):
        if not self.can_drive:
            return
        left, right = self._wheels()
        if (left, right) != (0, 0):
            changed = max(abs(left - self.last_wheels[0]), abs(right - self.last_wheels[1])) > CHANGE
            if not self.driving or changed or now - self.last_drive >= REPEAT_S:
                self.send(f"m {left} {right} {PULSE_MS}", None)
                self.driving, self.last_drive, self.last_wheels = True, now, (left, right)
        elif self.driving:
            self.driving, self.last_wheels = False, (0, 0)
            self.send("x", None)

    def _arm(self):
        dx = round(self.axes.get(DPAD_X, 0.0))
        dy = -round(self.axes.get(DPAD_Y, 0.0))      # up is negative
        moves = []
        if dx:
            moves.append(("base", -dx))              # a higher base angle points the arm left
        if dy:
            moves.append(("shoulder", dy))           # a higher shoulder angle raises it
        if "R2" in self.held:
            moves.append(("elbow", 1))
        if "L2" in self.held:
            moves.append(("elbow", -1))
        for joint, direction in moves:
            target = max(0, min(180, self.angles[joint] + direction * ARM_STEP_DEG))
            if target != self.angles[joint]:
                self.angles[joint] = target          # the reply corrects it if the sketch clamps
                self.send(f"{joint} {target}", self.on_reply)


# ---------------------------------------------------------------- reading the device

def _bits(event, kind):
    """Capability bits of an input device, from /sys (e.g. which axes it has)."""
    try:
        with open(f"/sys/class/input/{event}/device/capabilities/{kind}") as f:
            words = f.read().split()
    except OSError:
        return set()
    bits = set()
    for i, word in enumerate(reversed(words)):
        value = int(word, 16)
        bits.update(i * 64 + b for b in range(64) if value >> b & 1)
    return bits


def find_gamepad():
    """The first input device that looks like the robot's controller: (/dev path, name, axes)."""
    for sys_path in sorted(glob.glob("/sys/class/input/event*")):
        event = os.path.basename(sys_path)
        try:
            with open(f"{sys_path}/device/name") as f:
                name = f.read().strip()
        except OSError:
            continue
        if DEVICE_NAME.search(name) and BTN_SOUTH in _bits(event, "key"):
            return f"/dev/input/{event}", name, _bits(event, "abs")
    return None


def _abs_range(fd, code):
    import fcntl   # Linux only; imported here so PadLogic can be tested on any PC
    request = (2 << 30) | (24 << 16) | (ord("E") << 8) | (0x40 + code)   # EVIOCGABS(code)
    _, low, high, _, _, _ = struct.unpack("6i", fcntl.ioctl(fd, request, bytes(24)))
    return low, high


def _normalize(value, low_high):
    low, high = low_high
    half = (high - low) / 2 or 1
    return max(-1.0, min(1.0, (value - (low + high) / 2) / half))


class GamepadReader(threading.Thread):
    """Waits for the controller, reads it, and feeds PadLogic. Picks it up again after a reconnect."""

    def __init__(self, send):
        super().__init__(daemon=True, name="gamepad")
        self.logic = PadLogic(send)

    def run(self):
        while True:
            try:
                found = find_gamepad()
                if found:
                    self._serve(*found)
                else:
                    time.sleep(2)
            except Exception as exc:   # never take the relay down
                log.warning("gamepad: %s", exc)
                time.sleep(2)

    def _serve(self, path, name, axes):
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            ranges = {code: _abs_range(fd, code) for code in axes}
            if self.logic.connected(axes):
                log.info("gamepad connected: %s", name)
            else:
                log.warning("gamepad %s has no sticks; put it in D-input (Android) mode to drive", name)
            pending = b""
            while True:
                ready, _, _ = select.select([fd], [], [], 0.05)
                now = time.monotonic()
                if ready:
                    data = os.read(fd, EVENT.size * 64)   # raises OSError when the controller goes away
                    if not data:
                        raise OSError("device closed")
                    pending += data
                    while len(pending) >= EVENT.size:
                        _, _, kind, code, value = EVENT.unpack_from(pending)
                        pending = pending[EVENT.size:]
                        if kind == EV_ABS and code in ranges:
                            self.logic.axis(code, _normalize(value, ranges[code]), now)
                        elif kind == EV_KEY and code in BUTTONS:
                            self.logic.button(BUTTONS[code], value != 0, now)
                self.logic.tick(now)
        except OSError:
            log.info("gamepad disconnected: %s", name)
        finally:
            os.close(fd)
            self.logic.disconnected()


def test(seconds=None):
    """Prints the controller's buttons and sticks as they change, to check the map above."""
    found = find_gamepad()
    if not found:
        names = []
        for sys_path in sorted(glob.glob("/sys/class/input/event*")):
            try:
                with open(f"{sys_path}/device/name") as f:
                    names.append(f"{os.path.basename(sys_path)}: {f.read().strip()}")
            except OSError:
                pass
        print("No 8BitDo controller found. Is it on, paired and connected? Input devices:")
        print("\n".join("  " + n for n in names) or "  (none)")
        return 1
    path, name, axes = found
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    ranges = {code: _abs_range(fd, code) for code in axes}
    print(f"{name} at {path}")
    for code in sorted(ranges):
        print(f"  axis {ABS_NAMES.get(code, hex(code))}: {ranges[code][0]}..{ranges[code][1]}")
    print("Press buttons and move the sticks (Ctrl+C to stop):")
    last = {}
    end = time.monotonic() + seconds if seconds else None
    try:
        while end is None or time.monotonic() < end:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if not ready:
                continue
            data = os.read(fd, EVENT.size * 64)
            for i in range(0, len(data) - EVENT.size + 1, EVENT.size):
                _, _, kind, code, value = EVENT.unpack_from(data, i)
                if kind == EV_KEY:
                    label = BUTTONS.get(code, "not mapped")
                    print(f"  {KEY_NAMES.get(code, hex(code))} ({label}) {'down' if value else 'up'}", flush=True)
                elif kind == EV_ABS and code in ranges:
                    n = _normalize(value, ranges[code])
                    if abs(n - last.get(code, 99)) >= 0.25 or n in (-1.0, 0.0, 1.0):
                        last[code] = n
                        print(f"  {ABS_NAMES.get(code, hex(code))} {n:+.2f}", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)
    return 0


if __name__ == "__main__":
    raise SystemExit(test())
