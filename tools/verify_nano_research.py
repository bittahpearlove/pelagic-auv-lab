#!/usr/bin/env python3
"""Motor-disabled Nano forward-model HIL, timestamp/fault checks, timing and stack."""
import argparse
import ctypes
import csv
import importlib.util
import json
import math
from pathlib import Path
import time
import serial
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lab',ROOT/'lab/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def verify(port,output):
    lab=m.Lab();core=lab.core;m.research.bind(core)
    result=m.research.run_comparison(core,dict(m.DEFAULTS,noise=.005),lab.native_config,repeats=1,methods=['response'])
    rows=result['rows'];console=[];capture=[];maximum=[0.]*30;discrete_differences=0
    def send(text):ser.write((text+'\n').encode());ser.flush()
    def read_until(predicate,seconds=3):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            line=ser.readline().decode(errors='replace').strip()
            if line:console.append(line)
            if predicate(line):return line
        raise AssertionError('Nano reply timeout')
    def packet(seq,ms,acquired,z,v,temp,flags=1):
        # Same rounded observed inputs go to native and board.
        fields=[format(float(x),'.7g') for x in (z,v,temp)];send(f'P,{seq},{ms},{acquired},'+','.join(fields)+f',{flags}')
        line=read_until(lambda s:s.startswith(f'# PRF,{seq},'));parts=line[6:].split(',');assert len(parts)==35
        values=[float(x) for x in parts[2:]];return values,fields
    def begin():
        send('DISARM');read_until(lambda s:s=='# disarmed')
        send('PROF,4,2,2.5,0.1,0.005,175000');read_until(lambda s:s.startswith('# profile ready'))
    with serial.Serial(port,115200,timeout=.2) as ser:
        time.sleep(2);ser.reset_input_buffer();send('HELLO')
        identity=read_until(lambda s:s.startswith('# AUV Nano'))
        assert 'v0.15' in identity and 'simulated=1; motors=0' in identity
        features=read_until(lambda s:s.startswith('# FEATURES'))
        assert features=='# FEATURES,research=1,exploration=0'
        begin();assert core.lab_trial_config(4,2,2.5,.1,.005,175000)
        previous=0
        for seq,row in enumerate(rows,1):
            ms=int(row['ms']);acquired=int(row['acquired_ms'])
            values,fields=packet(seq,ms,acquired,row['depth_m'],row['vertical_mps'],row['temperature_raw_c'])
            inputs=(ctypes.c_float*9)(acquired,float(fields[2]),float(fields[0]),float(fields[1]),12,0,0,1,0)
            expected=(ctypes.c_float*30)();core.lab_trial_tick(ms,(ms-previous)/1000,inputs,expected);previous=ms
            for i in range(30):maximum[i]=max(maximum[i],abs(values[i]-expected[i]))
            assert int(values[0])==int(expected[0]) and values[1]==expected[1],(seq,values[:2],list(expected)[:2])
            if any(values[i]!=expected[i] for i in (6,7,15,16,22,23,24,25)):discrete_differences+=1
            assert abs(values[2]-expected[2])<.003 and abs(values[4]-expected[4])<.003
            assert all(math.isfinite(x) for x in values)
            capture.append(dict(sequence=seq,ms=ms,state=values[0],gradient=values[13],fit_valid=values[15],reason=values[16],decision_us=values[30],max_decision_us=values[31],stack_margin_bytes=values[32]))
        assert capture[-1]['state']==5
        assert discrete_differences==0,discrete_differences
        assert maximum[13]<.03 and maximum[12]<.002
        assert max(r['max_decision_us'] for r in capture)<50000
        assert min(r['stack_margin_bytes'] for r in capture)>200
        # Reordered sequence, stale acquisition, leak and missing link must stop.
        faults={}
        for name in ('sequence','stale','leak','timeout'):
            begin()
            if name=='timeout':
                line=read_until(lambda s:s.startswith('# PRF,0,'),seconds=2)
                data=[float(x) for x in line[6:].split(',')[2:]]
            else:
                packet(1,50,50,0,0,22)
                data,_=packet(1 if name=='sequence' else 2,550 if name=='stale' else 100,0 if name=='stale' else 100,0,0,22,3 if name=='leak' else 1)
            assert data[0]==6 and data[2]==0,(name,data)
            flag={'sequence':1,'stale':2,'leak':4,'timeout':2}[name];assert int(data[1])&flag
            faults[name]=int(data[1])
        send('DISARM');read_until(lambda s:s=='# disarmed')
    output.mkdir(parents=True,exist_ok=True)
    with (output/'nano_v015_research.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(capture[0]));w.writeheader();w.writerows(capture)
    summary=dict(verified=True,identity=identity,features=features,observations=len(capture),complete=True,
        max_absolute_native_difference=maximum,discrete_fit_policy_differences=discrete_differences,
        maximum_decision_us=max(r['max_decision_us'] for r in capture),minimum_stack_margin_bytes=min(r['stack_margin_bytes'] for r in capture),
        fault_checks=faults,final_state='disarmed',motors_enabled=False,
        limitations='Runtime measures decision function only, excluding UART formatting. Stack paint is an observed conservative unused margin, not a proof for every future driver.')
    (output/'nano_v015_research_verified.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'nano_v015_research_console.log').write_text('\n'.join(console)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',default='/dev/ttyUSB0');p.add_argument('--output',type=Path,default=ROOT/'output/logs');a=p.parse_args();verify(a.port,a.output)
