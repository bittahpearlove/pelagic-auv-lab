#!/usr/bin/env python3
"""Bench-only: actual Nano decides motion for virtual plant. No motor actuation."""
import ctypes
import csv
import importlib.util
import json
from pathlib import Path
import time
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('auv_lab',root/'lab/server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
(root/'output/logs').mkdir(parents=True,exist_ok=True)
lab=m.Lab();summary={}
with lab.lock:
    try:
        lab.action(dict(action='source',value='nano'));lab.action(dict(action='connect'))
        deadline=time.monotonic()+10
        while not lab.verified and time.monotonic()<deadline:lab.serial_tick();time.sleep(.01)
        assert lab.verified and lab.identity.startswith('v0.14'),lab.error or lab.identity
        identity=lab.identity
        lab.action(dict(action='explore_start',shape='tilted',center=1.3,width=.1,drop=3,tau=2,noise=0,profile_x=4))
        lab.core.lab_explore_begin();lab.core.lab_explore_tau(ctypes.c_float(2))
        sequence=None;expected=None;max_error=[0.0]*16;compared=0
        start=time.monotonic();before_change=None
        while lab.running and lab.ms<=320000:
            assert time.monotonic()-start<150,'Overall test deadline exceeded'
            lab.serial_tick()
            if lab.explore_reply is not None:
                assert expected is not None
                for i,(a,b) in enumerate(zip(lab.explore_reply,expected)):max_error[i]=max(max_error[i],abs(a-b))
                for i in (0,1,2,9,10,11,13,14,15):assert lab.explore_reply[i]==expected[i],(i,lab.explore_reply,expected)
                assert all(abs(lab.explore_reply[i]-expected[i])<.025 for i in (3,4,5,6,7,8)),(sequence,packet,lab.explore_reply,expected,max_error)
                compared+=1
            lab.exploration_tick()
            if lab.explore_pending is not None and lab.explore_pending!=sequence:
                sequence=lab.explore_pending
                packet=next(e['text'] for e in reversed(lab.console) if e['origin']=='TX' and e['text'].startswith('OBS,'))
                values=[float(v) for v in packet[4:].split(',')]
                inputs=(ctypes.c_float*5)(*values[2:]);out=(ctypes.c_float*16)()
                lab.core.lab_explore_tick(int(values[1]),inputs,out);expected=list(out)
            time.sleep(.001)
        assert not lab.running and not lab.explore_status['active'] and lab.explore_status['reason']==1,lab.explore_status
        assert lab.latest['depth_m']<=.14
        assert any(r['explore_phase']=='return' for r in lab.rows)
        assert any(r['explore_phase']=='ascend' for r in lab.rows)
        assert all(a['known_cells']<=b['known_cells'] for a,b in zip(lab.rows,list(lab.rows)[1:]))
        assert lab.explore_status['visits']>=1
        assert any(r['explore_phase']=='probe' for r in lab.rows)
        ascent=[r for r in lab.rows if r['explore_phase']=='backtrack']
        assert ascent and ascent[0]['depth_m']-min(r['depth_m'] for r in ascent)>.07
        first_transit=next(r['input_ms'] for r in lab.rows if r['explore_phase']=='transit')
        assert all(abs(r['x_m']-4)<.002 for r in lab.rows if r['input_ms']<first_transit and r['explore_phase'] in ('descend','backtrack'))
        assert any(r['gradient_2d_valid'] for r in lab.rows)
        assert any(r['explore_phase']=='transit' for r in lab.rows)
        for phase in ('backtrack','probe','transit'):
            since=None
            for row in lab.rows:
                if row['explore_phase']!=phase:since=None
                elif since is None:since=row['input_ms']
                else:assert row['input_ms']-since<=(10000 if phase=='transit' else 8000),(phase,row)

        summary=dict(verified=True,identity=identity,simulated_sensors=True,motor_outputs=False,
                     simulated_ms=lab.ms,wall_seconds=round(time.monotonic()-start,2),
                     observations=compared,local_rows=sum(r['transition'] for r in lab.rows),
                     gradient_rows=sum(r['gradient_2d_valid'] for r in lab.rows),
                     final=dict(lab.explore_status),parity_max_absolute_error=max_error,params=lab.params)
        with (root/'output/logs/nano_v014_exploration.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=m.FIELDS);w.writeheader();w.writerows(lab.rows)
        lab.action(dict(action='explore_start',shape='layer',drop=0))
        lab.action(dict(action='stop'))
        assert not lab.running and lab.explore_status['reason']==4
        summary['operator_stop']=dict(lab.explore_status)
        lab.send(b'DISARM\n');deadline=time.monotonic()+1
        while time.monotonic()<deadline:lab.serial_tick();time.sleep(.01)
        summary['disarm_ack']=any(e['text']=='# disarmed' for e in lab.console)
        assert summary['disarm_ack']
    finally:
        (root/'output/logs/nano_v014_console.log').write_text('\n'.join(str(e) for e in lab.console)+'\n')
        lab.disconnect()
        (root/'output/logs/nano_v014_verified.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
