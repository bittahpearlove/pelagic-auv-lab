#include <Arduino.h>
#include <Servo.h>
#include <string.h>
#include <stdlib.h>
#include "Config.h"
#include "ReportedConfig.h"
#include "Controller.h"
#include "Sensors.h"
#include "Explorer.h"
#ifdef __AVR__
#include <avr/wdt.h>
#include <avr/io.h>
// Disable an inherited watchdog before Arduino setup. Some Nano bootloaders
// still require updating to recover reliably from watchdog resets.
void watchdogEarly() __attribute__((naked, section(".init3"), used));
void watchdogEarly() { MCUSR = 0; wdt_disable(); }
#endif

Explorer explorer;
uint32_t explorerReceived=0;
Controller controller;
Sensors sensors;
Sample latest;
Servo leftEsc, rightEsc, verticalEsc;
uint32_t lastControl = 0, lastTelemetry = 0;
char command[96];
uint8_t commandLength = 0;
bool commandOverflow = false;

bool benchDemo = false;
bool demoAllowed() { return Config::SIMULATED_SENSORS && !Config::ENABLE_MOTOR_OUTPUTS; }
bool armPermit() { return (demoAllowed() && benchDemo) || digitalRead(Config::ARM_PIN) == LOW; }
bool leakTrip() { return !(demoAllowed() && benchDemo) && digitalRead(Config::LEAK_PIN) != LOW; }

void writeMotors() {
  if (!Config::ENABLE_MOTOR_OUTPUTS) return;
  const bool enabled = controller.active() && controller.state != State::Ready;
  const float thrust = enabled ? controller.verticalCommand : 0;
  leftEsc.writeMicroseconds(Config::ESC_NEUTRAL_US);
  rightEsc.writeMicroseconds(Config::ESC_NEUTRAL_US);
  verticalEsc.writeMicroseconds(Config::ESC_NEUTRAL_US +
      int(thrust * Config::VERTICAL_SIGN * Config::ESC_SPAN_US));
}

void printConfig() {
  Serial.print(F("# CONFIG"));
#define REPORT_VALUE(key, constant) Serial.print(F("," #key "=")); Serial.print(static_cast<float>(Config::constant), 4);
  AUV_BASE_REPORTED_CONFIG(REPORT_VALUE)
#undef REPORT_VALUE
  Serial.print(F(",water_shape=")); Serial.print(static_cast<int>(sensors.shape));
  Serial.print(F(",profile_x_m=")); Serial.println(sensors.profileX, 4);
}

void printIdentity() {
  Serial.print(F("# AUV Nano adaptive v0.12; simulated="));
  Serial.print(Config::SIMULATED_SENSORS ? 1 : 0);
  Serial.print(F("; motors="));
  Serial.println(Config::ENABLE_MOTOR_OUTPUTS ? 1 : 0);
  printConfig();
  Serial.println(F("ms,sample_ms,simulated,state,faults,valid,leak,temp_raw_c,temp_c,pressure_mbar,depth_raw_m,depth_m,vertical_mps,roll_deg,pitch_deg,voltage_v,current_a,target_depth_m,left_cmd,right_cmd,vertical_cmd,mode,speed_limit_mps,gradient_cpm,gradient_valid,transition,demo"));
}

// Strict bounded numeric packet parser; no dynamic String allocations on AVR.
bool parseNumbers(char* text,float* values,uint8_t count) {
  for(uint8_t i=0;i<count;i++) {
    char* end;values[i]=strtod(text,&end);
    if(end==text||!isfinite(values[i])||(i+1<count?*end!=',':*end!='\0'))return false;
    text=end+1;
  }
  return true;
}
// Parse sequence/time as integers: floats lose millisecond precision in long runs.
bool parseCounter(char*&text,uint32_t&value){
  if(*text<'0'||*text>'9')return false;
  uint32_t n=0;
  while(*text>='0'&&*text<='9'){
    const uint8_t digit=*text-'0';
    if(n>429496729UL||(n==429496729UL&&digit>5))return false;
    n=n*10+digit;text++;
  }
  if(*text!=',')return false;
  text++;value=n;return true;
}
void printExplorer(uint32_t sequence) {
  Serial.print(F("# EXP,"));Serial.print(sequence);
#define EXP_VALUE(value) Serial.print(','); Serial.print(static_cast<float>(value),4);
  EXP_VALUE(explorer.active) EXP_VALUE(explorer.local?explorer.phase:0) EXP_VALUE(explorer.reason)
  EXP_VALUE(explorer.surge) EXP_VALUE(explorer.heave) EXP_VALUE(explorer.targetX) EXP_VALUE(explorer.targetZ)
  EXP_VALUE(explorer.gx) EXP_VALUE(explorer.gz) EXP_VALUE(explorer.gradientValid) EXP_VALUE(explorer.visits) EXP_VALUE(explorer.phase) EXP_VALUE(explorer.distance) EXP_VALUE(explorer.localExit) EXP_VALUE(explorer.knownCells) EXP_VALUE(explorer.rechecks)
#undef EXP_VALUE
  Serial.println();
}
void handleCommand(uint32_t now) {
  if (!strncmp(command,"EXPL,",5)) {
    float v[2];
    if(demoAllowed()&&controller.state==State::Disarmed&&!explorer.active&&parseNumbers(command+5,v,2)&&v[0]==1&&v[1]>=.1f&&v[1]<=8){
      explorer.begin();explorer.tau=v[1];explorerReceived=now;
      Serial.println(F("# exploration ready; external measured observations required; motors disabled"));
    }else Serial.println(F("# exploration start rejected"));
  } else if (!strncmp(command,"OBS,",4)) {
    float v[5];char* fields=command+4;uint32_t sequence=0,ms=0;
    if(demoAllowed()&&explorer.active&&parseCounter(fields,sequence)&&sequence>0&&parseCounter(fields,ms)&&parseNumbers(fields,v,5)){
      ExplorationObservation o={v[0],v[1],v[2],v[3],v[4],ms};
      explorer.update(o);explorerReceived=now;printExplorer(sequence);
    }else {explorer.stop(3);Serial.println(F("# exploration observation rejected"));}
  } else if (!strcmp(command, "HELLO")) {
    printIdentity();
  } else if (!strcmp(command, "CONFIG")) {
    printConfig();
  } else if (!strncmp(command, "WATER", 5)) {
    if (demoAllowed() && controller.state == State::Disarmed && !explorer.active &&
        command[5] >= '0' && command[5] <= '4' && !command[6]) {
      sensors.shape = command[5] - '0';
      sensors.begin();
      Serial.println(F("# water shape selected"));
    } else Serial.println(F("# water rejected; disarm and use WATER0..4 in bench mode"));
  } else if (command[0] == 'X') {
    char* end;
    const float x = strtod(command + 1, &end);
    if (demoAllowed() && controller.state == State::Disarmed && !explorer.active && end != command + 1 &&
        !*end && isfinite(x) && x >= 0.5f && x <= 7.5f) {
      sensors.profileX = x;
      sensors.begin();
      Serial.println(F("# simulated profile x selected"));
    } else Serial.println(F("# x rejected; disarm and use X0.5..X7.5 in bench mode"));
  } else if (!strcmp(command, "DEMO")) {
    if (demoAllowed() && controller.state == State::Disarmed && !explorer.active) {
      sensors.begin();
      benchDemo = true;
      latest = sensors.read(now, 0, 0);
      controller.arm(latest, now, true);
      Serial.println(F("# simulation demo armed; starts in 5s; physical inputs simulated; motors disabled"));
    } else Serial.println(F("# demo rejected"));
  } else if (!strcmp(command, "ADAPT") || !strcmp(command, "FAST") || !strcmp(command, "SLOW")) {
    const ProfileMode requested = !strcmp(command, "ADAPT") ? ProfileMode::Adaptive :
                                 (!strcmp(command, "FAST") ? ProfileMode::Fast : ProfileMode::Slow);
    Serial.println(controller.selectMode(requested) ? F("# mode selected") : F("# disarm before changing mode"));
  } else if (!strcmp(command, "ARM")) {
    Serial.println((!explorer.active && controller.arm(latest, now, armPermit())) ? F("# armed") : F("# arm rejected"));
  } else if (!strcmp(command, "START")) {
    // Revalidate immediately; START may arrive between control ticks.
    if (controller.active() && (controller.check(latest, now) || !armPermit()))
      controller.stop(controller.check(latest, now) | (!armPermit() ? ARM_REMOVED : NONE));
    Serial.println(controller.start(now) ? F("# started") : F("# start rejected"));
  } else if (!strcmp(command, "STOP")) {
    explorer.stop(4);
    controller.stop(OPERATOR_STOP);
    benchDemo = false;
    Serial.println(F("# stopped; fault latched"));
  } else if (!strcmp(command, "DISARM")) {
    explorer.stop(4);
    controller.disarm();
    benchDemo = false;
    Serial.println(F("# disarmed"));
  } else if (!strcmp(command, "STATUS")) {
    lastTelemetry = now - Config::TELEMETRY_MS;
  } else {
    Serial.println(F("# commands: ARM START STOP DISARM STATUS HELLO CONFIG ADAPT FAST SLOW DEMO WATER0..4 X0.5..7.5 EXPL,adapt,tau,path_m OBS,seq,ms,x,z,vx,vz,T"));
  }
  writeMotors();
}

void readCommands(uint32_t now) {
  // Bound work per loop so a serial flood cannot starve control/watchdog.
  for (uint8_t budget = 0; budget < 32 && Serial.available(); ++budget) {
    const char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (!commandOverflow && commandLength) {
        command[commandLength] = '\0';
        handleCommand(now);
      } else if (commandOverflow) Serial.println(F("# command too long"));
      commandLength = 0;
      commandOverflow = false;
    } else if (!commandOverflow) {
      if (commandLength < sizeof(command) - 1) command[commandLength++] = c;
      else commandOverflow = true;
    }
  }
}

void telemetry(uint32_t now) {
  Serial.print(now); Serial.print(',');
  Serial.print(latest.acquiredMs); Serial.print(',');
  Serial.print(Config::SIMULATED_SENSORS ? 1 : 0); Serial.print(',');
  Serial.print(static_cast<uint8_t>(controller.state)); Serial.print(',');
  Serial.print(controller.faults); Serial.print(',');
  Serial.print(latest.valid ? 1 : 0); Serial.print(',');
  Serial.print(latest.leak ? 1 : 0); Serial.print(',');
  Serial.print(latest.temperatureRawC, 3); Serial.print(',');
  Serial.print(latest.temperatureC, 3); Serial.print(',');
  Serial.print(latest.pressureMbar, 3); Serial.print(',');
  Serial.print(latest.depthRawM, 3); Serial.print(',');
  Serial.print(latest.depthM, 3); Serial.print(',');
  Serial.print(latest.verticalMps, 3); Serial.print(',');
  Serial.print(latest.rollDeg, 2); Serial.print(',');
  Serial.print(latest.pitchDeg, 2); Serial.print(',');
  Serial.print(latest.voltageV, 3); Serial.print(',');
  Serial.print(latest.currentA, 3); Serial.print(',');
  Serial.print(controller.targetDepthM, 3); Serial.print(',');
  Serial.print(0); Serial.print(','); Serial.print(0); Serial.print(',');
  Serial.print(controller.verticalCommand, 3); Serial.print(',');
  Serial.print(static_cast<uint8_t>(controller.mode)); Serial.print(',');
  Serial.print(controller.speedLimitMps, 3); Serial.print(',');
  Serial.print(controller.sampler.gradientCpm, 3); Serial.print(',');
  Serial.print(controller.sampler.gradientValid ? 1 : 0); Serial.print(',');
  Serial.print(controller.sampler.transition ? 1 : 0); Serial.print(',');
  Serial.println(benchDemo ? 1 : 0);
}

void setup() {
  pinMode(Config::ARM_PIN, INPUT_PULLUP);
  pinMode(Config::LEAK_PIN, INPUT_PULLUP);
  pinMode(LED_BUILTIN, OUTPUT);
  if (Config::ENABLE_MOTOR_OUTPUTS) {
    leftEsc.attach(Config::LEFT_ESC_PIN);
    rightEsc.attach(Config::RIGHT_ESC_PIN);
    verticalEsc.attach(Config::VERTICAL_ESC_PIN);
    writeMotors();
  }
  Serial.begin(Config::SERIAL_BAUD);
  sensors.begin();
  printIdentity();
  lastControl = millis();
#ifdef __AVR__
  wdt_enable(WDTO_1S);
#endif
}

void loop() {
  const uint32_t now = millis();
  // Check hardware interlocks every loop, including between sensor samples.
  if (controller.active()) {
    uint16_t immediate = armPermit() ? NONE : ARM_REMOVED;
    if (leakTrip()) immediate |= LEAK;
    if (immediate) { controller.stop(immediate); writeMotors(); }
  }
  if (uint32_t(now - lastControl) >= Config::CONTROL_MS) {
    const float dt = bounded(uint32_t(now - lastControl) / 1000.0f, 0, 0.2f);
    lastControl = now;
    latest = sensors.read(now, controller.verticalCommand, dt);
    latest.leak = latest.leak || leakTrip();
    controller.update(latest, now, armPermit(), dt);
    if (demoAllowed() && benchDemo && controller.state == State::Ready) controller.start(now);
    writeMotors();
  }
  if(explorer.active&&uint32_t(now-explorerReceived)>1000){explorer.stop(5);Serial.println(F("# exploration stopped; observation link timeout"));printExplorer(0);}
  readCommands(now);
  digitalWrite(LED_BUILTIN, controller.active() ? HIGH : LOW);
  if (uint32_t(now - lastTelemetry) >= Config::TELEMETRY_MS) {
    lastTelemetry = now;
    telemetry(now);
  }
#ifdef __AVR__
  wdt_reset();
#endif
}
