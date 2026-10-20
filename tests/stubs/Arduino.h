#pragma once
#include <stdint.h>
#include <string>
#include <sstream>
#define F(x) x
#define LOW 0
#define HIGH 1
#define INPUT_PULLUP 2
#define OUTPUT 1
#define LED_BUILTIN 13
extern uint32_t fakeMs;
extern int pins[32];
inline uint32_t micros() { return fakeMs*1000; }
inline uint32_t millis() { return fakeMs; }
inline int digitalRead(int pin) { return pins[pin]; }
inline void digitalWrite(int pin, int value) { pins[pin] = value; }
inline void pinMode(int, int) {}
struct FakeSerial {
  std::string input;
  std::string output;
  void begin(unsigned long) {}
  int available() { return input.size(); }
  char read() { char c = input[0]; input.erase(0, 1); return c; }
  template<typename T> void print(T value) { std::ostringstream stream; stream << value; output += stream.str(); }
  template<typename T> void print(T value, int) { print(value); }
  void println() { output += "\n"; }
  template<typename T> void println(T value) { print(value); output += "\n"; }
  template<typename T> void println(T value, int digits) { print(value, digits); output += "\n"; }
};
extern FakeSerial Serial;
