#!/usr/bin/env python3
"""Deterministic native-controller comparisons; truth used only by evaluation."""
raise SystemExit('Archived v0.7 sweep benchmark. Saved results: output/experiments; policy source: archive/v07/Explorer.h. Current v0.8 missions have no sweep.')
import importlib.util,json,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lab',root/'lab/server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
lab=m.Lab();results=[];trajectories=[]
with lab.lock:
 for shape in ['flat','layer','tilted','front','patch','combined']:
  for name,adaptive,budget in [('dense_full',False,60),('dense_equal_budget',False,32),('adaptive',True,32)]:
   lab.reset();lab.action(dict(action='explore_start',adaptive=adaptive,path_budget=budget,shape='layer' if shape=='flat' else shape,center=1.3,drop=0 if shape in ('patch','flat') else 3,tau=2,noise=0))
   while lab.running:lab.exploration_tick()
   rows=list(lab.rows);report=lab.explore_status.copy();p=lab.params
   def temp(x,z):return lab.core.lab_water(x,z,m.SHAPES[p['shape']],p['center'],p['width'],p['drop'])
   def gradient(x,z):return math.hypot((temp(x+.005,z)-temp(x-.005,z))/.01,(temp(x,z+.005)-temp(x,z-.005))/.01)
   travel=report['travel'];gradient_samples=sum(gradient(r['x_m'],r['depth_m'])>=.5 for r in rows)
   follow_rows=sum(r['explore_phase']=='follow' for r in rows)
   peak=max(rows,key=lambda r:r['temperature_c'])
   result=dict(field=shape,policy=name,travel_m=travel,seconds=lab.ms/1000,detours=report['visits'],follow_rows=follow_rows,gradient_samples=gradient_samples,gradient_samples_per_m=gradient_samples/max(.001,travel),reason=report['reason'],peak_error_m=math.hypot(peak['x_m']-5.3,peak['depth_m']-1.65) if shape=='patch' else None)
   results.append(result);trajectories.append(dict(result=result,params=p.copy(),rows=[[r['x_m'],r['depth_m'],r['temperature_c']] for r in rows]))
(root/'output/experiments/exploration_comparison.json').write_text(json.dumps(results,indent=2)+'\n')
(root/'output/experiments/exploration_trajectories.json').write_text(json.dumps(trajectories)+'\n')
for r in results:print(r['field'],r['policy'],'distance',round(r['travel_m'],2),'time',r['seconds'],'detours',r['detours'],'follow',r['follow_rows'],'gradient readings/m',round(r['gradient_samples_per_m'],1))
