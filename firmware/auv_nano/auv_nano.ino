#include <Arduino.h>
#include <Servo.h>
#include <string.h>
#include <stdlib.h>
#include "Config.h"
#include "ReportedConfig.h"
#include "Controller.h"
#include "Sensors.h"
#include "Explorer.h"
#include "Diagnostics.h"
#ifdef __AVR__
#include <avr/wdt.h>
#include <avr/io.h>
// Disable an inherited watchdog before Arduino setup. Some Nano bootloaders
// still require updating to recover reliably from watchdog resets.
void watchdogEarly() __attribute__((naked, section(".init3"), used));
void watchdogEarly() { MCUSR = 0; wdt_disable(); }
#endif

#if AUV_HAS_EXPLORER
Explorer explorer;
uint32_t explorerReceived=0;
#endif
bool exploring(){
#if AUV_HAS_EXPLORER
 return explorer.active;
#else
 return false;
#endif
}
void stopExploration(uint8_t why){
#if AUV_HAS_EXPLORER
 explorer.stop(why);
#else
 (void)why;
#endif
}
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


#if AUV_HAS_RESEARCH
bool profileExternal=false;
uint32_t profileReceived=0,profileSequence=0,profilePrevious=0,profileStamp=0,decisionUs=0,maxDecisionUs=0;
bool profileHavePrevious=false;
void researchUpdate(const Sample&s,uint32_t now,float dt,bool permit=true){
  profileStamp=s.acquiredMs;
  const uint32_t started=micros();
  controller.update(s,now,permit,dt);
  if(benchDemo&&controller.state==State::Ready)controller.start(now);
  decisionUs=micros()-started;if(decisionUs>maxDecisionUs)maxDecisionUs=decisionUs;
}
void printResearch(uint32_t sequence){
  Serial.print(F("# PRF,"));Serial.print(sequence);Serial.print(',');Serial.print(profileStamp);
#define R_VALUE(value) Serial.print(',');Serial.print(static_cast<float>(value),4);
  R_VALUE(static_cast<int>(controller.state)) R_VALUE(controller.faults)
  R_VALUE(controller.verticalCommand) R_VALUE(controller.targetDepthM) R_VALUE(controller.speedLimitMps)
  R_VALUE(controller.reportedGradient())
  R_VALUE(controller.reportedGradientValid())
  R_VALUE(controller.reportedTransition())
  R_VALUE(static_cast<int>(controller.mode))
  R_VALUE(controller.sampler.regionValid) R_VALUE(controller.sampler.regionLow) R_VALUE(controller.sampler.regionHigh)
  R_VALUE(controller.estimator.temperature) R_VALUE(controller.estimator.gradient) R_VALUE(controller.estimator.residual)
  R_VALUE(controller.estimator.valid) R_VALUE(controller.policy.reason) R_VALUE(controller.estimator.gradientSigma)
  R_VALUE(controller.estimator.condition) R_VALUE(controller.estimator.span) R_VALUE(controller.settings.tauNominal)
  R_VALUE(controller.settings.tauMax) R_VALUE(controller.reachedBottom) R_VALUE(controller.budgetReturn)
  R_VALUE(controller.estimator.geometryValid) R_VALUE(controller.estimator.status)
  R_VALUE(controller.policy.modelLimit) R_VALUE(controller.policy.predictedLag)
  R_VALUE(controller.estimator.supportDepth) R_VALUE(controller.estimator.supportTemperature)
  R_VALUE(decisionUs) R_VALUE(maxDecisionUs) R_VALUE(stackMargin())
#undef R_VALUE
  Serial.println();
}
#endif
void printConfig() {
  Serial.print(F("# CONFIG"));
#define REPORT_VALUE(key, constant) Serial.print(F("," #key "=")); Serial.print(static_cast<float>(Config::constant), 4);
  AUV_BASE_REPORTED_CONFIG(REPORT_VALUE)
#undef REPORT_VALUE
  Serial.print(F(",water_shape=")); Serial.print(static_cast<int>(sensors.shape));
  Serial.print(F(",profile_x_m=")); Serial.println(sensors.profileX, 4);
}

void printIdentity() {
  Serial.print(F("# AUV Nano adaptive " AUV_VERSION "; simulated="));
  Serial.print(Config::SIMULATED_SENSORS ? 1 : 0);
  Serial.print(F("; motors="));
  Serial.println(Config::ENABLE_MOTOR_OUTPUTS ? 1 : 0);
  Serial.print(F("# FEATURES,research="));Serial.print(AUV_HAS_RESEARCH?1:0);
  Serial.print(F(",exploration="));Serial.println(AUV_HAS_EXPLORER?1:0);
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
#if AUV_HAS_EXPLORER
void printExplorer(uint32_t sequence) {
  Serial.print(F("# EXP,"));Serial.print(sequence);
#define EXP_VALUE(value) Serial.print(','); Serial.print(static_cast<float>(value),4);
  EXP_VALUE(explorer.active) EXP_VALUE(explorer.local?explorer.phase:0) EXP_VALUE(explorer.reason)
  EXP_VALUE(explorer.surge) EXP_VALUE(explorer.heave) EXP_VALUE(explorer.targetX) EXP_VALUE(explorer.targetZ)
  EXP_VALUE(explorer.gx) EXP_VALUE(explorer.gz) EXP_VALUE(explorer.gradientValid) EXP_VALUE(explorer.visits) EXP_VALUE(explorer.phase) EXP_VALUE(explorer.distance) EXP_VALUE(explorer.localExit) EXP_VALUE(explorer.knownCells) EXP_VALUE(0)
#undef EXP_VALUE
  Serial.println();
}
 #endif
void handleCommand(uint32_t now) {
#if AUV_HAS_RESEARCH
  if(!strncmp(command,"CAL,",4)){
    float v[4];
    if(demoAllowed()&&parseNumbers(command+4,v,4)&&controller.configure(v[0],v[1],v[2],v[3],Config::MISSION_TIMEOUT_MS))Serial.println(F("# calibration settings selected; provisional unless physically measured"));
    else Serial.println(F("# calibration settings rejected"));
    return;
  }
  if(!strncmp(command,"PROF,",5)){
    float v[6];
    if(demoAllowed()&&!exploring()&&controller.state==State::Disarmed&&parseNumbers(command+5,v,6)&&
       v[0]>=0&&v[0]<=5&&v[0]==floorf(v[0])&&v[5]==floorf(v[5])&&v[5]>=5000&&v[5]<=600000&&
       controller.configure(v[1],v[2],v[3],v[4],uint32_t(v[5]))&&controller.selectMode(static_cast<ProfileMode>(int(v[0])))){
      Sample s;s.valid=true;s.leak=false;s.voltageV=12;
      controller.arm(s,0,true);profileExternal=true;profileReceived=now;benchDemo=true;maxDecisionUs=0;profileSequence=0;profilePrevious=0;profileHavePrevious=false;
      Serial.println(F("# profile ready; external stamped observations; motors disabled"));
    }else Serial.println(F("# profile rejected"));
    return;
  }
  if(!strncmp(command,"P,",2)){
    char*fields=command+2;uint32_t seq=0,stamp=0,acquired=0;float v[4];
    if(demoAllowed()&&profileExternal&&parseCounter(fields,seq)&&seq&&parseCounter(fields,stamp)&&
       parseCounter(fields,acquired)&&parseNumbers(fields,v,4)&&v[3]>=0&&v[3]<=31&&v[3]==floorf(v[3])){
      Sample s;s.acquiredMs=acquired;s.depthRawM=s.depthM=v[0];s.verticalMps=v[1];
      s.temperatureRawC=s.temperatureC=v[2];s.pressureMbar=1013.25f+s.depthM*98.0665f;
      const uint8_t flags=uint8_t(v[3]);s.valid=flags&1;s.leak=flags&2;
      s.voltageV=(flags&4)?9:12;s.rollDeg=(flags&8)?40:0;s.currentA=(flags&16)?20:0;
      const uint32_t elapsed=stamp-profilePrevious;
      if(profileHavePrevious&&(!elapsed||elapsed>500||int32_t(seq-profileSequence)<=0)){
        controller.stop(INVALID_SENSOR);printResearch(seq);return;
      }
      const float dt=profileHavePrevious?elapsed*.001f:.05f;
      profileSequence=seq;profilePrevious=stamp;profileHavePrevious=true;
      researchUpdate(s,stamp,dt);profileReceived=now;printResearch(seq);
    }else{controller.stop(INVALID_SENSOR);profileExternal=false;benchDemo=false;Serial.println(F("# profile observation rejected"));}
    return;
  }
#endif

#if AUV_HAS_EXPLORER
  if (!strncmp(command,"EXPL,",5)) {
    float v[2];
    if(demoAllowed()&&controller.state==State::Disarmed&&!exploring()&&parseNumbers(command+5,v,2)&&v[0]==1&&v[1]>=.1f&&v[1]<=8){
      explorer.begin();explorer.tau=v[1];explorerReceived=now;
      Serial.println(F("# exploration ready; external measured observations required; motors disabled"));
    }else Serial.println(F("# exploration start rejected"));
  } else if (!strncmp(command,"OBS,",4)) {
    float v[5];char* fields=command+4;uint32_t sequence=0,ms=0;
    if(demoAllowed()&&explorer.active&&parseCounter(fields,sequence)&&sequence>0&&parseCounter(fields,ms)&&parseNumbers(fields,v,5)){
      ExplorationObservation o={v[0],v[1],v[2],v[3],v[4],ms};
      explorer.update(o);explorerReceived=now;printExplorer(sequence);
    }else {explorer.stop(3);Serial.println(F("# exploration observation rejected"));}
  } else
#endif
  if (!strcmp(command, "HELLO")) {
    printIdentity();
  } else if (!strcmp(command, "CONFIG")) {
    printConfig();
  } else if (!strncmp(command, "WATER", 5)) {
    if (demoAllowed() && controller.state == State::Disarmed && !exploring() &&
        command[5] >= '0' && command[5] <= '4' && !command[6]) {
      sensors.shape = command[5] - '0';
      sensors.begin();
      Serial.println(F("# water shape selected"));
    } else Serial.println(F("# water rejected; disarm and use WATER0..4 in bench mode"));
  } else if (command[0] == 'X') {
    char* end;
    const float x = strtod(command + 1, &end);
    if (demoAllowed() && controller.state == State::Disarmed && !exploring() && end != command + 1 &&
        !*end && isfinite(x) && x >= 0.5f && x <= 7.5f) {
      sensors.profileX = x;
      sensors.begin();
      Serial.println(F("# simulated profile x selected"));
    } else Serial.println(F("# x rejected; disarm and use X0.5..X7.5 in bench mode"));
  } else if (!strcmp(command, "DEMO")) {
    if (demoAllowed() && controller.state == State::Disarmed && !exploring()) {
      sensors.begin();
      benchDemo = true;
      latest = sensors.read(now, 0, 0);
      controller.arm(latest, now, true);
      Serial.println(F("# simulation demo armed; starts in 5s; physical inputs simulated; motors disabled"));
    } else Serial.println(F("# demo rejected"));
  } else if (!strcmp(command, "ADAPT") || !strcmp(command, "FAST") || !strcmp(command, "SLOW") || !strcmp(command,"MEDIUM") || !strcmp(command,"LAG") || !strcmp(command,"UNGATED")) {
    const ProfileMode requested = !strcmp(command, "ADAPT") ? ProfileMode::Adaptive :
                                 (!strcmp(command, "FAST") ? ProfileMode::Fast : !strcmp(command,"MEDIUM")?ProfileMode::Medium:!strcmp(command,"LAG")?ProfileMode::Response:!strcmp(command,"UNGATED")?ProfileMode::ResponseUngated:ProfileMode::Slow);
    Serial.println(controller.selectMode(requested) ? F("# mode selected") : F("# disarm before changing mode"));
  } else if (!strcmp(command, "ARM")) {
    Serial.println((!exploring() && controller.arm(latest, now, armPermit())) ? F("# armed") : F("# arm rejected"));
  } else if (!strcmp(command, "START")) {
    // Revalidate immediately; START may arrive between control ticks.
    if (controller.active() && (controller.check(latest, now) || !armPermit()))
      controller.stop(controller.check(latest, now) | (!armPermit() ? ARM_REMOVED : NONE));
    Serial.println(controller.start(now) ? F("# started") : F("# start rejected"));
  } else if (!strcmp(command, "STOP")) {
    stopExploration(4);
#if AUV_HAS_RESEARCH
    profileExternal=false;
#endif
    controller.stop(OPERATOR_STOP);
    benchDemo = false;
    Serial.println(F("# stopped; fault latched"));
  } else if (!strcmp(command, "DISARM")) {
    stopExploration(4);
#if AUV_HAS_RESEARCH
    profileExternal=false;
#endif
    controller.disarm();
    benchDemo = false;
    Serial.println(F("# disarmed"));
  } else if (!strcmp(command, "STATUS")) {
    lastTelemetry = now - Config::TELEMETRY_MS;
  } else {
    Serial.println(F("# commands: ARM START STOP DISARM STATUS HELLO CONFIG ADAPT FAST SLOW MEDIUM LAG UNGATED DEMO CAL,tau,tmax,eps,noise PROF,mode,tau,tmax,eps,noise,ms P,seq,ms,acquired,z,v,T,flags WATER0..4 X0.5..7.5 EXPL,adapt,tau OBS,seq,ms,x,z,vx,vz,T"));
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
#if AUV_HAS_RESEARCH
  if(!profileExternal)printResearch(0);
#endif
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
  Serial.print(controller.reportedGradient(), 3); Serial.print(',');
  Serial.print(controller.reportedGradientValid() ? 1 : 0); Serial.print(',');
  Serial.print(controller.reportedTransition() ? 1 : 0); Serial.print(',');
  Serial.println(benchDemo ? 1 : 0);
}

void setup() {
  paintStack();
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
  if (
#if AUV_HAS_RESEARCH
      !profileExternal&&
#endif
      uint32_t(now - lastControl) >= Config::CONTROL_MS) {
    const float dt = bounded(uint32_t(now - lastControl) / 1000.0f, 0, 0.2f);
    lastControl = now;
    latest = sensors.read(now, controller.verticalCommand, dt);
    latest.leak = latest.leak || leakTrip();
#if AUV_HAS_RESEARCH
    researchUpdate(latest,now,dt,armPermit());
#else
    controller.update(latest, now, armPermit(), dt);
#endif
    if (demoAllowed() && benchDemo && controller.state == State::Ready) controller.start(now);
    writeMotors();
  }
#if AUV_HAS_EXPLORER
  if(explorer.active&&uint32_t(now-explorerReceived)>1000){explorer.stop(5);Serial.println(F("# exploration stopped; observation link timeout"));printExplorer(0);}
#endif
#if AUV_HAS_RESEARCH
  if(profileExternal&&controller.active()&&uint32_t(now-profileReceived)>1000){
    controller.stop(STALE_SENSOR);profileExternal=false;benchDemo=false;printResearch(0);
  }
#endif
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
