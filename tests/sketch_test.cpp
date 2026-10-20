#include <cassert>
#include <iostream>
#include "../firmware/auv_nano/auv_nano.ino"
uint32_t fakeMs = 0;
int pins[32] = {};
FakeSerial Serial;
void tick(uint32_t ms) { fakeMs = ms; loop(); }
void send(const char* cmd) { Serial.input = cmd; loop(); }
int main() {
  setup();
  send("DISARM\n");send("EXPL,1,2\n");
  send("OBS,4294967295,4294967200,2,0.35,0,0,22\n");loop();assert(explorer.active);
  send("OBS,1,4,2,0.35,0,0,22\n");loop();assert(explorer.active);
  send("OBS,2,4294967296,2,0.35,0,0,22\n");loop();assert(!explorer.active&&explorer.reason==3);
  assert(verticalEsc.attached == -1 && leftEsc.attached == -1 && rightEsc.attached == -1);
  Serial.output.clear();
  send("HELLO\n");
  assert(Serial.output.find("# AUV Nano adaptive v0.14; simulated=1; motors=0") != std::string::npos);
  assert(Serial.output.find("# CONFIG,target_depth_m=") != std::string::npos);
  assert(Serial.output.find(",probe_tau_s=2") != std::string::npos);
  assert(Serial.output.find("ms,sample_ms,") != std::string::npos);
  assert(controller.state == State::Disarmed && verticalEsc.attached == -1);
  send("WATER4\n"); assert(sensors.shape == 4);
  send("X5.3\n"); assert(sensors.profileX > 5.29f && sensors.profileX < 5.31f);
  send("Xnan\n"); send("X8\n"); send("X2bad\n"); send("WATER9\n");
  assert(sensors.shape == 4 && sensors.profileX > 5.29f);
  send("WATER0\n"); send("X4\n");
  tick(50);
  send("ARM\n"); assert(controller.state == State::Ready);
  send("START\n"); assert(controller.state == State::Ready);
  tick(5050); send("START\n"); assert(controller.state == State::Descend);
  tick(5100); assert(controller.verticalCommand > 0);
  send("WATER4\n"); send("X5.3\n");
  assert(sensors.shape == 0 && sensors.profileX == 4); // Configuration cannot change while active.
  const float beforeConfig = controller.verticalCommand;
  Serial.output.clear(); send("CONFIG\n");
  assert(Serial.output.find("# CONFIG,target_depth_m=") != std::string::npos);
  assert(controller.state == State::Descend && controller.verticalCommand == beforeConfig);
  pins[Config::LEAK_PIN] = HIGH;
  tick(5101); assert(controller.state == State::Fault && controller.verticalCommand == 0);
  pins[Config::LEAK_PIN] = LOW;
  send("ARM\n"); assert(controller.state == State::Fault);
  send("DISARM\n"); send("ARM\n"); assert(controller.state == State::Ready);
  pins[Config::ARM_PIN] = HIGH;
  tick(5102); assert(controller.state == State::Fault && (controller.faults & ARM_REMOVED));
  pins[Config::ARM_PIN] = LOW;
  send("DISARM\n");
  send("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXARM\n"); loop(); loop(); loop(); assert(controller.state == State::Disarmed);
  send("ARM\n"); assert(controller.state == State::Ready);
  send("STOP\n"); assert(controller.state == State::Fault && controller.verticalCommand == 0);
  send("DISARM\n"); send("SLOW\n"); assert(controller.mode == ProfileMode::Slow);
  send("ADAPT\n"); assert(controller.mode == ProfileMode::Adaptive);
  pins[Config::ARM_PIN] = HIGH; pins[Config::LEAK_PIN] = HIGH;
  send("DEMO\n"); assert(benchDemo && controller.state == State::Ready);
  send("FAST\n"); assert(controller.mode == ProfileMode::Adaptive);
  tick(10200); assert(controller.state == State::Descend);
  send("STOP\n"); assert(!benchDemo && controller.state == State::Fault);
  assert(!armPermit() && leakTrip());
  send("DISARM\n");send("EXPL,1,2\n");assert(explorer.active);
  send("OBS,1,0,2,0.35,0,0,22\n");loop();
  assert(explorer.active && Serial.output.find("# EXP,1,")!=std::string::npos);
  send("OBS,1000001,310000,2,0.35,0,0,22\n");loop();assert(explorer.active);
  send("OBS,2,310000,2,0.35,0,0,22\n");loop();assert(!explorer.active&&explorer.reason==3);
  send("EXPL,1,2\n");send("OBS,3,100,2,nan,0,0,22\n");loop();assert(!explorer.active);
  send("EXPL,1,2\n");tick(11401);assert(!explorer.active&&explorer.reason==5);
  send("EXPL,1,2\n");send("ARM\n");assert(controller.state==State::Disarmed);
  send("STOP\n");assert(!explorer.active&&explorer.surge==0&&explorer.heave==0);
  send("DISARM\n");send("EXPL,1,2\n");
  send("OBS,4294967295,4294967200,2,0.35,0,0,22\n");loop();assert(explorer.active);
  send("OBS,1,4,2,0.35,0,0,22\n");loop();assert(explorer.active);
  send("OBS,2,4294967296,2,0.35,0,0,22\n");loop();assert(!explorer.active&&explorer.reason==3);
  assert(verticalEsc.attached == -1 && leftEsc.attached == -1 && rightEsc.attached == -1);
  std::cout << "PASS: sketch commands, ESC disabled, immediate interlocks, overflow rejection\n";
}
