#pragma once
#include <stdint.h>
#ifdef __AVR__
#include <avr/io.h>
#include <avr/interrupt.h>
extern char __heap_start;
extern char* __brkval;
inline void paintStack(){
  const uint8_t saved=SREG;cli();
  volatile uint8_t* end=reinterpret_cast<uint8_t*>(SP-64);
  for(volatile uint8_t*p=reinterpret_cast<uint8_t*>(&__heap_start);p<end;p++)*p=0xa5;
  SREG=saved;
}
inline int stackMargin(){
  // Lower bound from untouched painted bytes; includes instrumentation's stack.
  uint8_t*p=reinterpret_cast<uint8_t*>(&__heap_start);
  const uint8_t* end=reinterpret_cast<uint8_t*>(SP-64);
  const uint8_t* start=p;while(p<end&&*p==0xa5)++p;
  return int(p-start);
}
#else
inline void paintStack(){}
inline int stackMargin(){return -1;}
#endif
