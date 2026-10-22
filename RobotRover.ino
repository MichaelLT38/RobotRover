/*
  RobotRover.ino - drive + robot arm controller for the Arduino UNO Q
  (runs on the UNO Q's STM32 microcontroller; upload with Arduino IDE 2,
   board package "Arduino Q Boards")

  Commands can come from two places:
    1. The Serial Monitor (type them in, line ending "New Line")
    2. The phone app, over Bluetooth. The board's Linux side runs board/robot_ble_bridge.py,
       which passes each command to this sketch through the Bridge as a call to "robot".

  Hardware this sketch assumes (change the pin/channel numbers below to match yours):
    - Two DC wheel motors on a dual H-bridge motor driver (TB6612FNG or L298N).
      The front ball caster needs no code.
    - Four hobby servos on a PCA9685 16-channel servo driver board (I2C):
        channel 0 = base (rotates left/right)
        channel 1 = shoulder (first arm segment)
        channel 2 = elbow (second arm segment)
        channel 3 = gripper (opens/closes)
    - Separate battery power for the motors and for the servos.
      Do NOT power motors or servos from the UNO Q's 5V pin. Connect all grounds together.

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
#include "RobotMatrix.h"

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

int driveSpeed = 180;              // 0-255
unsigned long driveStopAt = 0;     // millis() time to stop at, 0 = keep driving

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

const int GRIPPER_OPEN   = 30;
const int GRIPPER_CLOSED = 120;

struct Joint {
  const char* name;
  uint8_t channel;
  int minAngle;     // safety limits so the arm can't hit itself or the chassis
  int maxAngle;
  int homeAngle;
  int current;      // where the servo is now
  int target;       // where it's moving to
};

enum { BASE, SHOULDER, ELBOW, GRIPPER, JOINT_COUNT };

Joint joints[JOINT_COUNT] = {
  // name        ch  min  max  home  (current, target start at home)
  { "base",      0,   0, 180,  90,            90,  90 },
  { "shoulder",  1,  15, 165,  90,            90,  90 },
  { "elbow",     2,  15, 165,  90,            90,  90 },
  { "gripper",   3,  GRIPPER_OPEN, GRIPPER_CLOSED, GRIPPER_OPEN, GRIPPER_OPEN, GRIPPER_OPEN },
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
void drive(int left, int right, unsigned long durationMs) {
  setMotor(LEFT_PWM,  LEFT_IN1,  LEFT_IN2,  left,  LEFT_REVERSED);
  setMotor(RIGHT_PWM, RIGHT_IN1, RIGHT_IN2, right, RIGHT_REVERSED);
  driveStopAt = (durationMs > 0) ? millis() + durationMs : 0;
}

void stopDriving() {
  drive(0, 0, 0);
}

// Called every loop: stops the wheels when a timed drive runs out
void updateDrive() {
  if (driveStopAt != 0 && (long)(millis() - driveStopAt) >= 0) {
    stopDriving();
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

// Called every loop: moves each servo one degree toward its target
void updateArm() {
  static unsigned long lastStep = 0;
  if (millis() - lastStep < SERVO_STEP_MS) return;
  lastStep = millis();

  for (int i = 0; i < JOINT_COUNT; i++) {
    Joint& j = joints[i];
    if (j.current == j.target) continue;
    j.current += (j.target > j.current) ? 1 : -1;
    writeServo(j.channel, j.current);
  }
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
  Monitor.println("  speed N  set drive speed 0-255");
  Monitor.println("Arm (angles in degrees):");
  Monitor.println("  base N   shoulder N   elbow N   grip N");
  Monitor.println("  open     close        home");
  Monitor.println("Other:");
  Monitor.println("  pos      show arm positions");
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

  // Show it on the LED matrix
  RobotMatrix::onCommand(cmd, hasValue, value);

  // ---- Driving ----
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
  if (cmd == "help" || cmd == "?") { printHelp(); return "help printed to Serial Monitor"; }

  return "unknown: " + line;
}

// Called by the Linux side (phone -> Bluetooth -> robot_ble_bridge.py -> Bridge).
// Registered with provide_safe, so it runs between loop() passes, never mid-loop.
String bridgeCommand(String line) {
  return handleCommand(line);
}

// Collects characters typed in the Serial Monitor until Enter, then runs the command
void readMonitorCommands() {
  static String buffer;
  while (Monitor.available() > 0) {
    char c = (char)Monitor.read();
    if (c == '\n' || c == '\r') {
      if (buffer.length() > 0) {
        Monitor.println(handleCommand(buffer));
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
  // Motor pins first, and stopped, so the wheels don't twitch at power-on
  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(LEFT_PWM, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);
  pinMode(RIGHT_PWM, OUTPUT);
  stopDriving();

  RobotMatrix::begin();

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

  // Servos don't report their position, so at power-on they jump to home.
  // Keep clear of the arm when switching on.
  for (int i = 0; i < JOINT_COUNT; i++) {
    writeServo(joints[i].channel, joints[i].current);
  }

  Monitor.println("Ready.");
  printHelp();
}

void loop() {
  readMonitorCommands();
  updateDrive();
  updateArm();

  // LED matrix follows the servos' real positions
  int angles[JOINT_COUNT];
  for (int i = 0; i < JOINT_COUNT; i++) angles[i] = joints[i].current;
  RobotMatrix::update(angles, driveSpeed);
  // Phone commands are handled automatically right after each loop() pass
}
