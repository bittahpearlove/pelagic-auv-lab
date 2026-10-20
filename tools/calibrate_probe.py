#!/usr/bin/env python3
"""Fit one isolated probe step response. Input: time_s,temperature_c after immersion."""
import argparse
import csv
import json
import math
from pathlib import Path

def fit_step(times,values):
    if len(times)<20 or len(times)!=len(values) or not all(math.isfinite(v) for v in times+values):raise ValueError('Need at least 20 finite readings')
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Times must increase strictly')
    t=[v-times[0] for v in times];n=len(t);sy=sum(values);best=None
    # Profile least squares: solve endpoint and amplitude for each candidate tau.
    for i in range(800):
        tau=.05*(1200**(i/799));x=[math.exp(-v/tau) for v in t];sx=sum(x);sxx=sum(v*v for v in x);sxy=sum(a*b for a,b in zip(x,values));det=n*sxx-sx*sx
        if det<=1e-10:continue
        a=(sy*sxx-sx*sxy)/det;b=(n*sxy-sx*sy)/det
        residual=sum((y-a-b*v)**2 for y,v in zip(values,x))
        if best is None or residual<best[0]:best=(residual,tau,a,b)
    residual,tau,a,b=best
    if abs(b)<.2:raise ValueError('Step amplitude below 0.2 °C; identify a measurable step')
    return dict(tau_s=tau,endpoint_c=a,initial_c=a+b,amplitude_c=-b,residual_rmse_c=math.sqrt(residual/n),duration_s=t[-1],samples=n,
        duration_at_least_five_tau=t[-1]>=5*tau,fit_hits_search_edge=tau<=.051 or tau>=59,
        interpretation='First-order least-squares model fit; no uncertainty interval or physical certification. Repeat at representative flow and in both directions.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('csv',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():p.error('Refusing to overwrite a calibration result')
    with args.csv.open() as f:rows=list(csv.DictReader(f))
    result=fit_step([float(r['time_s']) for r in rows],[float(r['temperature_c']) for r in rows])
    result['source']=args.csv.name;args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
