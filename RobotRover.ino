/*
  RobotRover.ino - drive + robot arm controller for the Arduino UNO Q
  (runs on the UNO Q's STM32 microcontroller; upload with Arduino IDE 2,
   board package "Arduino Q Boards")

  Commands can come from two places:
    1. The Serial Monitor (type them in, line ending "New Line")
    2. The board's Linux side, which runs board/robot_ble_bridge.py. It takes commands from
       the phone app or desktop page over Bluetooth LE, and from a paired 8BitDo gamepad, and
       passes each one to this sketch through the Bridge as a call to "robot".

  Hardware this sketch assumes (change the pin/channel numbers below to match yours):
    - Two DC wheel motors on a dual H-bridge motor driver (TB6612FNG or L298N).
      The front ball caster needs no code.
    - Four hobby servos on a PCA9685 16-channel servo driver board (I2C):
        channel 0 = base (rotates left/right)
        channel 1 = shoulder (first arm segment)
        channel 2 = elbow (second arm segment)
        channel 3 = gripper (opens/closes)
    - One 2S Li-ion pack (7.4 V) behind a main switch. The motors run straight from it;
      the servos and the board each get their own 5 V regulator (the board's feeds its
      5V pin). Never power motors or servos from the UNO Q itself. Connect all grounds.
    - A 20k / 10k divider from the pack to A0 for the battery gauge (see BATTERY_SENSE).

  Libraries (install from Library Manager):
    - Arduino_RouterBridge          (Bridge + Serial Monitor on the UNO Q)
    - Adafruit PWM Servo Driver Library
  (Arduino_LED_Matrix comes with the "Arduino Q Boards" package.)

  The board's LED matrix shows what's happening: an icon for each command,
  then a robot face that reacts. See RobotMatrix.h.
*/

#include <Arduino_RouterBridge.h>
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <zephyr/kernel.h>
#include "RobotMatrix.h"

// Phone commands may run on the Bridge's own thread instead of between loop()
// passes, so commands and loop() take turns through this lock. Command handlers
// only change targets and flags; all pin and I2C writes happen in loop().
struct k_mutex robotLock;

// =====================================================================
//  Wheel motors
// =====================================================================

// Left motor
const int LEFT_PWM  = 5;   // ENA (L298N) or PWMA (TB6612). Must be a PWM (~) pin.
const int LEFT_IN1  = 7;
const int LEFT_IN2  = 8;

// Right motor
const int RIGHT_PWM = 6;   // ENB (L298N) or PWMB (TB6612). Must be a PWM (~) pin.
const int RIGHT_IN1 = 4;
const int RIGHT_IN2 = 2;

// Set to true if a wheel spins backwards when you drive forward
const bool LEFT_REVERSED  = false;
const bool RIGHT_REVERSED = false;

// How long a drive command lasts if you don't give a time (milliseconds).
// The phone app sends short repeated pulses while you hold a button, so if
// Bluetooth drops out the robot stops by itself a moment later.
const unsigned long DEFAULT_DRIVE_MS = 1000;

// Wheels speed up gradually instead of jumping to full power, which cuts the
// current surge at every start. Every RAMP_TICK_MS the output moves RAMP_STEP
// closer to the target: 0 -> 255 takes about 150 ms. Slowing down, stopping
// and reversing are instant (with both inputs low the driver lets the motor
// coast, so dropping the power causes no surge).
const unsigned long RAMP_TICK_MS = 10;
const int RAMP_STEP = 17;

int driveSpeed = 180;              // 0-255
unsigned long driveStopAt = 0;     // millis() time to stop at, 0 = keep driving
int targetLeft = 0, targetRight = 0;   // what the last command asked for, -255..255
int outLeft = 0, outRight = 0;         // what the motor pins are doing now

// =====================================================================
//  Arm servos
// =====================================================================

Adafruit_PWMServoDriver servoBoard;   // default I2C address 0x40
const uint8_t SERVO_BOARD_ADDR = 0x40;

// Pulse widths for 0 and 180 degrees. Many servos use 500-2500, some 1000-2000.
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2500;

// Arm moves 1 degree every SERVO_STEP_MS, so it glides instead of snapping.
// Smaller number = faster arm.
const unsigned long SERVO_STEP_MS = 15;

// At power-on the servos jump to home one at a time, this far apart,
// so they don't all draw their start-up current at once.
const unsigned long SERVO_STARTUP_GAP_MS = 250;

// A joint that sits still at its relaxAt angle for this long stops getting
// pulses and goes limp, so it stops drawing holding current and humming.
// Its next command turns it back on.
const unsigned long SERVO_RELAX_MS = 3000;
const int RELAX_NEVER = -1;

const int GRIPPER_OPEN   = 30;
const int GRIPPER_CLOSED = 120;

struct Joint {
  const char* name;
  uint8_t channel;
  int minAngle;     // safety limits so the arm can't hit itself or the chassis
  int maxAngle;
  int homeAngle;
  int relaxAt;      // angle where the joint may go limp when idle, or RELAX_NEVER
  int current;      // where the servo is now
  int target;       // where it's moving to
  bool relaxed = false;         // pulses are off (servo limp)
  bool wake = false;            // a command arrived: hold position again
  unsigned long stillSince = 0; // when it last moved or was commanded
};

enum { BASE, SHOULDER, ELBOW, GRIPPER, JOINT_COUNT };

// Only the gripper relaxes, and only when open, so it never drops what it holds.
// The base stays powered because the arm can get knocked while driving, and the
// shoulder and elbow hold the arm up.
Joint joints[JOINT_COUNT] = {
  // name        ch  min  max  home  relaxAt       (current, target start at home)
  { "base",      0,   0, 180,  90,  RELAX_NEVER,    90,  90 },
  { "shoulder",  1,  15, 165,  90,  RELAX_NEVER,    90,  90 },
  { "elbow",     2,  15, 165,  90,  RELAX_NEVER,    90,  90 },
  { "gripper",   3,  GRIPPER_OPEN, GRIPPER_CLOSED, GRIPPER_OPEN, GRIPPER_OPEN, GRIPPER_OPEN, GRIPPER_OPEN },
};

// =====================================================================
//  Motor functions
// =====================================================================

// speed: -255 (full reverse) to 255 (full forward), 0 = stop
void setMotor(int pwmPin, int in1, int in2, int speed, bool reversed) {
  if (reversed) speed = -speed;
  speed = constrain(speed, -255, 255);

  digitalWrite(in1, speed > 0 ? HIGH : LOW);
  digitalWrite(in2, speed < 0 ? HIGH : LOW);
  analogWrite(pwmPin, speed >= 0 ? speed : -speed);
}

// Drive both wheels. durationMs = 0 means keep going until told to stop.
// Only sets the targets; updateDrive() in loop() moves the motors.
void drive(int left, int right, unsigned long durationMs) {
  targetLeft = left;
  targetRight = right;
  driveStopAt = (durationMs > 0) ? millis() + durationMs : 0;
}

void stopDriving() {
  drive(0, 0, 0);
}

// One ramp step from out toward target. step = 0 still allows the instant drops.
int rampToward(int out, int target, int step) {
  if ((out > 0 && target < 0) || (out < 0 && target > 0)) out = 0;   // reversing: coast first
  if (abs(target) <= abs(out)) return target;                        // slowing or stopping: now
  return target > 0 ? min(out + step, target) : max(out - step, target);
}

// Called every loop: ends timed drives and ramps the motors toward their targets
void updateDrive() {
  if (driveStopAt != 0 && (long)(millis() - driveStopAt) >= 0) {
    stopDriving();
  }

  static unsigned long lastTick = 0;
  int step = 0;
  if (millis() - lastTick >= RAMP_TICK_MS) {
    lastTick = millis();
    step = RAMP_STEP;
  }

  int left = rampToward(outLeft, targetLeft, step);
  int right = rampToward(outRight, targetRight, step);
  if (left != outLeft || right != outRight) {
    outLeft = left;
    outRight = right;
    setMotor(LEFT_PWM,  LEFT_IN1,  LEFT_IN2,  outLeft,  LEFT_REVERSED);
    setMotor(RIGHT_PWM, RIGHT_IN1, RIGHT_IN2, outRight, RIGHT_REVERSED);
  }
}

// =====================================================================
//  Servo functions
// =====================================================================

void writeServo(uint8_t channel, int angle) {
  int us = map(angle, 0, 180, SERVO_MIN_US, SERVO_MAX_US);
  servoBoard.writeMicroseconds(channel, us);
}

// Sets where a joint should move to. Returns a short reply for the user.
String setJointTarget(int index, int angle) {
  Joint& j = joints[index];
  int clamped = constrain(angle, j.minAngle, j.maxAngle);
  j.target = clamped;
  j.wake = true;    // updateArm() turns a relaxed servo back on

  String reply = String(j.name) + " -> " + String(clamped);
  if (clamped != angle) {
    reply += " (limit " + String(j.minAngle) + "-" + String(j.maxAngle) + ")";
  }
  return reply;
}

void goHome() {
  for (int i = 0; i < JOINT_COUNT; i++) {
    setJointTarget(i, joints[i].homeAngle);
  }
}

// Called every loop: moves each servo one degree toward its target,
// and lets idle joints go limp (or wakes them) as set in the joints table
void updateArm() {
  static unsigned long lastStep = 0;
  if (millis() - lastStep < SERVO_STEP_MS) return;
  lastStep = millis();
  unsigned long now = lastStep;

  for (int i = 0; i < JOINT_COUNT; i++) {
    Joint& j = joints[i];
    if (j.current != j.target) {
      j.current += (j.target > j.current) ? 1 : -1;
      writeServo(j.channel, j.current);
      j.relaxed = false;
      j.wake = false;
      j.stillSince = now;
    } else if (j.wake) {
      if (j.relaxed) writeServo(j.channel, j.current);
      j.relaxed = false;
      j.wake = false;
      j.stillSince = now;
    } else if (!j.relaxed && j.current == j.relaxAt && now - j.stillSince >= SERVO_RELAX_MS) {
      servoBoard.setPWM(j.channel, 0, 4096);   // PCA9685 "full off": no pulses
      j.relaxed = true;
    }
  }
}

// =====================================================================
//  Battery gauge
// =====================================================================
//
// A 20k / 10k divider from the pack's + (after the main switch) to A0 lets the
// sketch read the 2S pack: 8.4 V full reads 2.8 V at the pin. When the pack
// is low the matrix shows a battery now and then; when it's empty, nothing
// that moves is allowed until it's charged.

// Set true once the divider is wired. With nothing on A0 the pin floats and
// would give random readings.
const bool BATTERY_SENSE = false;

const int   BATT_PIN = A0;
const float BATT_DIVIDER = 3.0;        // (20k + 10k) / 10k: must match the resistors
const float BATT_CAL = 1.00;           // tweak until "batt" matches a multimeter
const float ADC_REF_V = 3.3;
const int   ADC_BITS = 12;
const float BATT_FULL_V = 8.2;         // charge bar full
const float BATT_LOW_V = 7.0;          // 3.5 V per cell
const float BATT_EMPTY_V = 6.6;        // 3.3 V per cell; the pack's own protection cuts off at about 6.0 V
const float BATT_ABSENT_V = 3.0;       // below this, nothing is connected (pack switched off, USB only)
const float BATT_HYST_V = 0.2;         // a state clears only this far above its threshold
const unsigned long BATT_SAMPLE_MS = 200;
const unsigned long BATT_EMPTY_HOLD_MS = 3000;   // must stay below empty this long
const float BATT_SMOOTHING = 0.1;      // each sample moves the average 10%, about 2 s

float battVolts = 0;
RobotMatrix::Battery battState = RobotMatrix::BATT_NONE;

// Set by "poweroff", which the relay sends just before it shuts Linux down
bool poweringOff = false;

float readPackVolts() {
  int raw = analogRead(BATT_PIN);
  return raw * ADC_REF_V / ((1 << ADC_BITS) - 1) * BATT_DIVIDER * BATT_CAL;
}

// Charge bar length for the matrix icon, 0-7 pixels
int batteryFill() {
  return constrain((int)lroundf((battVolts - BATT_EMPTY_V) / (BATT_FULL_V - BATT_EMPTY_V) * 7), 0, 7);
}

// Called every loop: samples the pack and updates the state
void updateBattery() {
  if (!BATTERY_SENSE) return;
  static unsigned long lastSample = 0, emptySince = 0;
  static bool countingEmpty = false;
  unsigned long now = millis();
  if (now - lastSample < BATT_SAMPLE_MS) return;
  lastSample = now;

  // Smooth over motor surges, but follow at once when a pack appears or disappears
  float v = readPackVolts();
  if (battState == RobotMatrix::BATT_NONE || v < BATT_ABSENT_V) battVolts = v;
  else battVolts += (v - battVolts) * BATT_SMOOTHING;

  RobotMatrix::Battery next;
  if (battVolts < BATT_ABSENT_V)     next = RobotMatrix::BATT_NONE;
  else if (battVolts < BATT_EMPTY_V) next = RobotMatrix::BATT_EMPTY;
  else if (battVolts < BATT_LOW_V)   next = RobotMatrix::BATT_LOW;
  else                               next = RobotMatrix::BATT_OK;

  // Stay in a worse state until the voltage is clearly back above its threshold
  if (battState == RobotMatrix::BATT_EMPTY && next != RobotMatrix::BATT_NONE &&
      battVolts < BATT_EMPTY_V + BATT_HYST_V) next = RobotMatrix::BATT_EMPTY;
  if (battState == RobotMatrix::BATT_LOW && next == RobotMatrix::BATT_OK &&
      battVolts < BATT_LOW_V + BATT_HYST_V) next = RobotMatrix::BATT_LOW;

  // Only call it empty once it has lasted BATT_EMPTY_HOLD_MS
  if (next == RobotMatrix::BATT_EMPTY && battState != RobotMatrix::BATT_EMPTY) {
    if (!countingEmpty) { countingEmpty = true; emptySince = now; }
    if (now - emptySince < BATT_EMPTY_HOLD_MS) next = RobotMatrix::BATT_LOW;
  } else {
    countingEmpty = false;
  }

  if (next == RobotMatrix::BATT_EMPTY && battState != RobotMatrix::BATT_EMPTY) {
    stopDriving();
  }
  battState = next;
  RobotMatrix::setBattery(battState, batteryFill());
}

// Reply for the "batt" command, e.g. "battery 7.62 V ok"
String batteryText() {
  if (!BATTERY_SENSE) return "battery sensing off (set BATTERY_SENSE in the sketch)";
  if (battState == RobotMatrix::BATT_NONE) return "battery not connected";
  const char* word = battState == RobotMatrix::BATT_OK  ? "ok"
                   : battState == RobotMatrix::BATT_LOW ? "low" : "empty";
  return "battery " + String(battVolts, 2) + " V " + word;
}

// =====================================================================
//  Commands (shared by the Serial Monitor and the phone)
// =====================================================================

void printHelp() {
  Monitor.println();
  Monitor.println("=== Robot commands ===");
  Monitor.println("Driving (optional time in ms, 0 = until 'x'):");
  Monitor.println("  w [ms]   forward          s [ms]   backward");
  Monitor.println("  a [ms]   spin left        d [ms]   spin right");
  Monitor.println("  x        stop");
  Monitor.println("  m L R [ms]  tank drive: left and right wheel -255..255");
  Monitor.println("  speed N  set drive speed 0-255");
  Monitor.println("Arm (angles in degrees):");
  Monitor.println("  base N   shoulder N   elbow N   grip N");
  Monitor.println("  open     close        home");
  Monitor.println("Other:");
  Monitor.println("  pos      show arm positions");
  Monitor.println("  batt     show battery voltage");
  Monitor.println("  poweroff get ready to be switched off (poweroff 0 cancels)");
  Monitor.println("  help     show this list");
  Monitor.println();
}

// Short one-line status, e.g. "base 90 shoulder 90 elbow 90 gripper 30 speed 180"
String positionsText() {
  String text;
  for (int i = 0; i < JOINT_COUNT; i++) {
    text += String(joints[i].name) + " " + String(joints[i].target) + " ";
  }
  text += "speed " + String(driveSpeed);
  return text;
}

// Commands that move a wheel or a servo (refused when the battery is empty
// or while powering off)
bool movesSomething(const String& cmd) {
  return cmd == "w" || cmd == "s" || cmd == "a" || cmd == "d" || cmd == "m" ||
         cmd == "base" || cmd == "shoulder" || cmd == "elbow" || cmd == "grip" ||
         cmd == "open" || cmd == "close" || cmd == "home";
}

// Reads up to maxCount whole numbers from text like "180 -120 400"; returns how many it found
int parseNumbers(const String& text, long out[], int maxCount) {
  const char* p = text.c_str();
  int n = 0;
  while (n < maxCount) {
    char* end;
    long v = strtol(p, &end, 10);
    if (end == p) break;
    out[n++] = v;
    p = end;
  }
  return n;
}

// The matrix shows a tank drive ("m left right") like the matching arrow command
const char* tankIcon(long left, long right) {
  if (left == 0 && right == 0) return "x";
  if (left >= 0 && right >= 0) return "w";
  if (left <= 0 && right <= 0) return "s";
  return left < right ? "a" : "d";
}

// Runs one command and returns a short reply (kept short so it fits in a Bluetooth message)
String handleCommand(String line) {
  line.trim();
  line.toLowerCase();
  if (line.length() == 0) return "";

  // Split "cmd 123" into the word and the number
  String cmd = line;
  long value = 0;
  bool hasValue = false;
  int space = line.indexOf(' ');
  if (space > 0) {
    cmd = line.substring(0, space);
    String num = line.substring(space + 1);
    num.trim();
    if (num.length() > 0) {
      value = num.toInt();
      hasValue = true;
    }
  }

  unsigned long ms = hasValue ? (unsigned long)max(0L, value) : DEFAULT_DRIVE_MS;

  // Tank drive "m left right [ms]": each wheel -255..255 (sent by the gamepad's sticks)
  long tank[3] = {0, 0, (long)DEFAULT_DRIVE_MS};
  int tankCount = (cmd == "m" && space > 0) ? parseNumbers(line.substring(space + 1), tank, 3) : 0;

  // ---- Power off: the relay sends this just before it shuts Linux down ----
  if (cmd == "poweroff") {
    RobotMatrix::onCommand(cmd, hasValue, value);
    if (hasValue && value == 0) {       // the relay couldn't shut down after all
      poweringOff = false;
      RobotMatrix::setPoweringOff(false);
      return "power-off cancelled";
    }
    stopDriving();
    poweringOff = true;
    RobotMatrix::setPoweringOff(true);
    return "powering off";
  }
  if (poweringOff && movesSomething(cmd)) return "powering off";

  // Nothing moves on an empty battery
  if (battState == RobotMatrix::BATT_EMPTY && movesSomething(cmd)) {
    RobotMatrix::onCommand("batt", false, 0);
    return "battery empty " + String(battVolts, 1) + " V, charge me";
  }

  // Show it on the LED matrix
  if (tankCount >= 2) RobotMatrix::onCommand(tankIcon(tank[0], tank[1]), false, 0);
  else RobotMatrix::onCommand(cmd, hasValue, value);

  // ---- Driving ----
  if (cmd == "m" && tankCount >= 2) {
    int left = constrain((int)tank[0], -255, 255);
    int right = constrain((int)tank[1], -255, 255);
    drive(left, right, tankCount == 3 ? (unsigned long)max(0L, tank[2]) : DEFAULT_DRIVE_MS);
    return "wheels " + String(left) + " " + String(right);
  }
  if (cmd == "w") { drive( driveSpeed,  driveSpeed, ms); return "forward"; }
  if (cmd == "s") { drive(-driveSpeed, -driveSpeed, ms); return "backward"; }
  if (cmd == "a") { drive(-driveSpeed,  driveSpeed, ms); return "spin left"; }
  if (cmd == "d") { drive( driveSpeed, -driveSpeed, ms); return "spin right"; }
  if (cmd == "x" || cmd == "stop") { stopDriving(); return "stopped"; }
  if (cmd == "speed" && hasValue) {
    driveSpeed = constrain((int)value, 0, 255);
    return "speed " + String(driveSpeed);
  }

  // ---- Arm ----
  if (cmd == "base"     && hasValue) return setJointTarget(BASE, value);
  if (cmd == "shoulder" && hasValue) return setJointTarget(SHOULDER, value);
  if (cmd == "elbow"    && hasValue) return setJointTarget(ELBOW, value);
  if (cmd == "grip"     && hasValue) return setJointTarget(GRIPPER, value);
  if (cmd == "open")  { setJointTarget(GRIPPER, GRIPPER_OPEN);   return "gripper opening"; }
  if (cmd == "close") { setJointTarget(GRIPPER, GRIPPER_CLOSED); return "gripper closing"; }
  if (cmd == "home")  { goHome(); return "arm going home"; }

  // ---- Other ----
  if (cmd == "pos") return positionsText();
  if (cmd == "batt") return batteryText();
  if (cmd == "help" || cmd == "?") { printHelp(); return "help printed to Serial Monitor"; }

  return "unknown: " + line;
}

// Runs one command while holding robotLock, so it never overlaps loop()'s updates
String runCommand(const String& line) {
  k_mutex_lock(&robotLock, K_FOREVER);
  String reply = handleCommand(line);
  k_mutex_unlock(&robotLock);
  return reply;
}

// Called by the Linux side (phone -> Bluetooth -> robot_ble_bridge.py -> Bridge).
// Registered with provide_safe, which is meant to run it between loop() passes;
// robotLock keeps it safe even if the Bridge runs it on its own thread.
String bridgeCommand(String line) {
  return runCommand(line);
}

// Collects characters typed in the Serial Monitor until Enter, then runs the command
void readMonitorCommands() {
  static String buffer;
  while (Monitor.available() > 0) {
    char c = (char)Monitor.read();
    if (c == '\n' || c == '\r') {
      if (buffer.length() > 0) {
        Monitor.println(runCommand(buffer));
        buffer = "";
      }
    } else if (buffer.length() < 40) {
      buffer += c;
    }
  }
}

// =====================================================================
//  Setup and main loop
// =====================================================================

void setup() {
  // Before anything can call runCommand()
  k_mutex_init(&robotLock);

  // Motor pins first, and stopped, so the wheels don't twitch at power-on
  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(LEFT_PWM, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);
  pinMode(RIGHT_PWM, OUTPUT);
  setMotor(LEFT_PWM,  LEFT_IN1,  LEFT_IN2,  0, LEFT_REVERSED);
  setMotor(RIGHT_PWM, RIGHT_IN1, RIGHT_IN2, 0, RIGHT_REVERSED);

  RobotMatrix::begin();
  analogReadResolution(ADC_BITS);   // battery gauge (default is 10-bit)

  Bridge.begin();
  Monitor.begin();
  delay(500);
  Monitor.println("RobotRover starting...");

  // Let the Linux side (and so the phone) send commands
  if (!Bridge.provide_safe("robot", bridgeCommand)) {
    Monitor.println("WARNING: could not register 'robot' with the Bridge. Phone control won't work.");
  }

  // Servo board
  servoBoard.begin();
  servoBoard.setOscillatorFrequency(27000000);
  servoBoard.setPWMFreq(50);   // standard 50 Hz for hobby servos

  Wire.beginTransmission(SERVO_BOARD_ADDR);
  if (Wire.endTransmission() != 0) {
    Monitor.println("WARNING: PCA9685 servo board not found. Check SDA/SCL wiring and power.");
  }

  // Servos don't report their position, so at power-on they jump to home,
  // one at a time to spread out the current. Keep clear of the arm when switching on.
  for (int i = 0; i < JOINT_COUNT; i++) {
    writeServo(joints[i].channel, joints[i].current);
    delay(SERVO_STARTUP_GAP_MS);
  }
  for (int i = 0; i < JOINT_COUNT; i++) joints[i].stillSince = millis();

  Monitor.println("Ready.");
  printHelp();
}

void loop() {
  readMonitorCommands();

  k_mutex_lock(&robotLock, K_FOREVER);
  updateBattery();
  updateDrive();
  updateArm();

  // LED matrix follows the servos' real positions
  int angles[JOINT_COUNT];
  for (int i = 0; i < JOINT_COUNT; i++) angles[i] = joints[i].current;
  RobotMatrix::update(angles, driveSpeed);
  k_mutex_unlock(&robotLock);
  // Phone commands are handled right after each loop() pass (or on the Bridge's thread)
}
