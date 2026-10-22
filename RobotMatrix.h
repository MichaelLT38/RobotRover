/*
  RobotMatrix.h - "face + icons" display for the UNO Q's 13x8 LED matrix

  - Each command flashes an icon (arrows, stop sign, joint dial, claw, house...).
    The icon stays up while the command keeps repeating (holding a drive button,
    dragging a slider).
  - Then the robot face reacts for a few seconds (looks where you drove,
    squints when the gripper closes, smiles after "home"...).
  - When nothing is happening, it shows a calm face that blinks and glances around.

  The joint dial and claw follow the servos' actual positions, so you can see
  the arm catching up to a command.

  desktop/index.html has a JavaScript copy of this design for the demo preview.
  If you change shapes or timings here, change them there too.
*/
#pragma once

#include <Arduino.h>
#include <Arduino_LED_Matrix.h>
#include <math.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace RobotMatrix {

const int W = 13;                      // columns
const int H = 8;                       // rows
const uint8_t MAX_BRIGHT = 7;          // 3-bit grayscale: 0 (off) to 7 (full)
const unsigned long FRAME_MS = 40;     // ~25 frames per second
const unsigned long REACT_MS = 2500;   // how long the face reacts after an icon

enum Event { EV_NONE, EV_FWD, EV_BACK, EV_LEFT, EV_RIGHT, EV_STOP, EV_JOINT,
             EV_GRIP, EV_HOME, EV_SPEED, EV_POS, EV_UNKNOWN };
enum Mood  { M_NEUTRAL, M_WIDE, M_SQUINT, M_HAPPY, M_CONFUSED };

Arduino_LED_Matrix matrix;
uint8_t frame[W * H];

Event event = EV_NONE;
int eventJoint = 0;                    // 0 base, 1 shoulder, 2 elbow
unsigned long eventAt = 0;             // when the latest command arrived
Mood mood = M_NEUTRAL;                 // face reaction after the icon
int lookX = 0, lookY = 0;              // where the pupils point (-1, 0, 1)
unsigned long lastFrame = 0;

// ------------------------------------------------------------------
//  Drawing helpers
// ------------------------------------------------------------------

inline void px(int x, int y, uint8_t v) {
  if (x < 0 || x >= W || y < 0 || y >= H) return;
  uint8_t& p = frame[y * W + x];
  if (v > p) p = v;
}

// rows: 8 strings of 13 chars. '#' = v, '1'-'7' = that brightness, anything else = off
void pattern(const char* const rows[H], uint8_t v) {
  for (int y = 0; y < H; y++)
    for (int x = 0; x < W && rows[y][x]; x++) {
      char c = rows[y][x];
      if (c == '#') px(x, y, v);
      else if (c >= '1' && c <= '7') px(x, y, c - '0');
    }
}

void line(float x0, float y0, float x1, float y1, uint8_t v) {
  int n = (int)(fmaxf(fabsf(x1 - x0), fabsf(y1 - y0)) * 2) + 1;
  for (int i = 0; i <= n; i++) {
    float t = (float)i / n;
    px((int)lroundf(x0 + (x1 - x0) * t), (int)lroundf(y0 + (y1 - y0) * t), v);
  }
}

// 3x5 letters for the joint dial
void letter(char c, int ox, int oy, uint8_t v) {
  static const char* const B[5] = { "##.", "#.#", "##.", "#.#", "##." };
  static const char* const S[5] = { "###", "#..", "###", "..#", "###" };
  static const char* const E[5] = { "###", "#..", "##.", "#..", "###" };
  const char* const* g = (c == 'B') ? B : (c == 'S') ? S : E;
  for (int y = 0; y < 5; y++)
    for (int x = 0; x < 3; x++)
      if (g[y][x] == '#') px(ox + x, oy + y, v);
}

// ------------------------------------------------------------------
//  Icons
// ------------------------------------------------------------------

// Moving chevrons. dir: 0 up, 1 down, 2 left, 3 right
void chevrons(int dir, unsigned long now) {
  int phase = (now / 100) % 5;
  for (int j = -1; j < 4; j++) {
    int o = j * 5 - phase + 2;
    for (int k = 0; k < 4; k++) {
      if (dir <= 1) {                               // vertical
        int y = o + k;
        if (dir == 1) y = (H - 1) - y;
        px(6 - k, y, MAX_BRIGHT);
        px(6 + k, y, MAX_BRIGHT);
      } else {                                      // horizontal
        int x = o + k;
        if (dir == 3) x = (W - 1) - x;
        px(x, 3 - k, MAX_BRIGHT);
        px(x, 4 + k, MAX_BRIGHT);
      }
    }
  }
}

void stopSign(unsigned long now) {
  static const char* const rows[H] = {
    ".....###.....",
    "....#####....",
    "...#######...",
    "...#######...",
    "...#######...",
    "...#######...",
    "....#####....",
    ".....###.....",
  };
  pattern(rows, ((now / 200) % 2) ? 3 : MAX_BRIGHT);   // pulses
}

// Joint letter + half-circle dial with a needle at the servo's angle
void jointDial(int joint, int angle) {
  letter("BSE"[joint], 0, 1, MAX_BRIGHT);
  const float cx = 8, cy = 7, r = 4;
  for (int a = 0; a <= 180; a += 15) {
    float rad = a * (float)M_PI / 180.0f;
    px((int)lroundf(cx + r * cosf(rad)), (int)lroundf(cy - r * sinf(rad)), 2);
  }
  float rad = angle * (float)M_PI / 180.0f;
  line(cx, cy, cx + r * cosf(rad), cy - r * sinf(rad), MAX_BRIGHT);
}

// Gripper claw. gripAngle 30 (open) .. 120 (closed)
void claw(int gripAngle) {
  int gap = (int)lroundf(4.0f - 3.0f * (constrain(gripAngle, 30, 120) - 30) / 90.0f);
  for (int y = 0; y < 4; y++) {
    px(6 - gap - 1, y, MAX_BRIGHT);
    px(6 + gap + 1, y, MAX_BRIGHT);
  }
  px(6 - gap, 0, MAX_BRIGHT);                       // jaw tips
  px(6 + gap, 0, MAX_BRIGHT);
  for (int x = 6 - gap - 1; x <= 6 + gap + 1; x++) px(x, 4, MAX_BRIGHT);
  for (int y = 5; y < H; y++) px(6, y, MAX_BRIGHT); // wrist
}

void house() {
  static const char* const rows[H] = {
    "......#......",
    ".....###.....",
    "....#####....",
    "...#######...",
    "..#########..",
    "...#.....#...",
    "...#..##.#...",
    "...#######...",
  };
  pattern(rows, MAX_BRIGHT);
}

// Speed bar plus dots that stream past faster at higher speed
void speedBar(int speed, unsigned long now) {
  int len = (int)lroundf(13.0f * constrain(speed, 0, 255) / 255.0f);
  for (int x = 0; x < W; x++) {
    px(x, 3, x < len ? MAX_BRIGHT : 1);
    px(x, 4, x < len ? MAX_BRIGHT : 1);
  }
  int off = (int)(((uint64_t)now * (speed + 1) / 20000) % W);
  for (int k = 0; k < 3; k++) {
    px((off + k * 5) % W, 1, 5);
    px((off + k * 5) % W, 6, 5);
  }
}

void question() {
  static const char* const rows[H] = {
    ".....###.....",
    "....#...#....",
    "........#....",
    ".......#.....",
    "......#......",
    "......#......",
    ".............",
    "......#......",
  };
  pattern(rows, MAX_BRIGHT);
}

// ------------------------------------------------------------------
//  Face
// ------------------------------------------------------------------

void face(Mood m, int dx, int dy, bool blink) {
  const int eyes[2] = { 3, 9 };
  for (int e = 0; e < 2; e++) {
    int ex = eyes[e];
    bool squint = (m == M_SQUINT) || (m == M_CONFUSED && e == 0);
    if (m == M_HAPPY) {                             // ^ ^
      px(ex - 1, 3, MAX_BRIGHT);
      px(ex, 2, MAX_BRIGHT);
      px(ex + 1, 3, MAX_BRIGHT);
    } else if (squint || blink) {                   // - -
      for (int x = ex - 1; x <= ex + 1; x++) px(x, 3, blink ? 5 : MAX_BRIGHT);
    } else {                                        // eye with a pupil
      for (int y = 1; y <= 4; y++)
        for (int x = ex - 1; x <= ex + 1; x++) px(x, y, m == M_WIDE ? 3 : 2);
      px(ex + dx, 2 + dy, MAX_BRIGHT);
      px(ex + dx, 3 + dy, MAX_BRIGHT);
    }
  }
  switch (m) {
    case M_HAPPY:    px(4, 5, 7); px(5, 6, 7); px(6, 6, 7); px(7, 6, 7); px(8, 5, 7); break;
    case M_WIDE:     px(6, 5, 6); px(5, 6, 6); px(7, 6, 6); px(6, 7, 6); break;
    case M_CONFUSED: px(4, 6, 5); px(5, 5, 5); px(6, 6, 5); px(7, 5, 5); px(8, 6, 5); break;
    default:         px(5, 6, 4); px(6, 6, 4); px(7, 6, 4); break;
  }
}

// Calm face that blinks every few seconds and glances left and right now and then
void idleFace(unsigned long now) {
  bool blink = (now % 4000) < 150;
  unsigned long g = now % 9000;
  int dx = (g >= 6000 && g < 6800) ? -1 : (g >= 6800 && g < 7600) ? 1 : 0;
  face(M_NEUTRAL, dx, 0, blink);
}

// ------------------------------------------------------------------
//  Public API
// ------------------------------------------------------------------

unsigned long iconDuration(Event e) {
  switch (e) {
    case EV_FWD: case EV_BACK: case EV_LEFT: case EV_RIGHT: return 600;   // refreshed by each drive pulse
    case EV_STOP:    return 700;
    case EV_JOINT: case EV_GRIP: case EV_SPEED: case EV_HOME: return 1200;
    case EV_UNKNOWN: return 1500;
    default:         return 0;                                            // EV_POS: straight to the face
  }
}

void begin() {
  matrix.begin();
  matrix.setGrayscaleBits(3);   // brightness values 0-7
  memset(frame, 0, sizeof(frame));
  matrix.draw(frame);
}

// Call once per command (from handleCommand) with the parsed word and number
void onCommand(const String& cmd, bool hasValue, long value) {
  Event e = EV_UNKNOWN;
  Mood m = M_NEUTRAL;
  int lx = 0, ly = 0;

  if      (cmd == "w") { e = EV_FWD;   ly = -1; }
  else if (cmd == "s") { e = EV_BACK;  ly = 1; }
  else if (cmd == "a") { e = EV_LEFT;  lx = -1; }
  else if (cmd == "d") { e = EV_RIGHT; lx = 1; }
  else if (cmd == "x" || cmd == "stop") { e = EV_STOP; m = M_WIDE; }
  else if (cmd == "base" && hasValue) {
    e = EV_JOINT; eventJoint = 0;
    lx = value > 100 ? -1 : (value < 80 ? 1 : 0);
  }
  else if ((cmd == "shoulder" || cmd == "elbow") && hasValue) {
    e = EV_JOINT; eventJoint = (cmd == "shoulder") ? 1 : 2;
    ly = value > 90 ? -1 : 1;
  }
  else if (cmd == "grip" && hasValue) { e = EV_GRIP; m = value >= 75 ? M_SQUINT : M_WIDE; }
  else if (cmd == "open")  { e = EV_GRIP; m = M_WIDE; }
  else if (cmd == "close") { e = EV_GRIP; m = M_SQUINT; }
  else if (cmd == "home")  { e = EV_HOME; m = M_HAPPY; }
  else if (cmd == "speed" && hasValue) { e = EV_SPEED; m = value > 200 ? M_WIDE : M_NEUTRAL; }
  else if (cmd == "pos" || cmd == "help" || cmd == "?") { e = EV_POS; lx = 1; ly = -1; }
  else { m = M_CONFUSED; }

  event = e;
  mood = m;
  lookX = lx;
  lookY = ly;
  eventAt = millis();
}

// Call every loop(). angles: current base, shoulder, elbow, gripper servo angles.
void update(const int angles[4], int speed) {
  unsigned long now = millis();
  if (now - lastFrame < FRAME_MS) return;
  lastFrame = now;

  memset(frame, 0, sizeof(frame));
  unsigned long since = now - eventAt;
  unsigned long iconMs = iconDuration(event);

  if (event != EV_NONE && since < iconMs) {
    switch (event) {
      case EV_FWD:     chevrons(0, now); break;
      case EV_BACK:    chevrons(1, now); break;
      case EV_LEFT:    chevrons(2, now); break;
      case EV_RIGHT:   chevrons(3, now); break;
      case EV_STOP:    stopSign(now); break;
      case EV_JOINT:   jointDial(eventJoint, angles[eventJoint]); break;
      case EV_GRIP:    claw(angles[3]); break;
      case EV_HOME:    house(); break;
      case EV_SPEED:   speedBar(speed, now); break;
      case EV_UNKNOWN: question(); break;
      default: break;
    }
  } else if (event != EV_NONE && since < iconMs + REACT_MS) {
    face(mood, lookX, lookY, false);
  } else {
    idleFace(now);
  }

  matrix.draw(frame);
}

}  // namespace RobotMatrix
