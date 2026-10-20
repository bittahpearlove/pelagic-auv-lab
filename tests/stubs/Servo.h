#pragma once
struct Servo {
  int attached = -1;
  int pulse = 0;
  void attach(int pin) { attached = pin; }
  void writeMicroseconds(int value) { pulse = value; }
};
