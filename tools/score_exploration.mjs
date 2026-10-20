import fs from 'node:fs/promises';
import {ThermalMap,temperatureAt,trueGradient} from '../lab/static/thermal-map.mjs';
const file=new URL('../output/experiments/exploration_trajectories.json',import.meta.url),runs=JSON.parse(await fs.readFile(file,'utf8'));
for(const run of runs){
 const map=new ThermalMap(),gradientBins=new Set();for(const r of run.rows){map.add(...r);const g=trueGradient(r[0],r[1],run.params);if(Math.hypot(g.gx,g.gz)>=.5)gradientBins.add(`${Math.floor(r[0]/.1)}:${Math.floor(r[1]/.1)}`);}
 let sum=0,count=0,gradSum=0,gradCount=0,gradTotal=0,nnSum=0;
 for(let iz=0;iz<16;iz++)for(let ix=0;ix<40;ix++){
  const x=.4+(ix+.5)/40*7.2,z=.2+(iz+.5)/16*2.5,t=temperatureAt(x,z,run.params),g=trueGradient(x,z,run.params),isGrad=Math.hypot(g.gx,g.gz)>=.5,e=map.estimate(x,z);
  if(isGrad)gradTotal++;
  if(e?.gradient&&e.coverage>.15){sum+=(e.temperature-t)**2;count++;if(isGrad){gradSum+=(e.temperature-t)**2;gradCount++;}}
  const nearest=run.rows.reduce((a,b)=>(b[0]-x)**2+(b[1]-z)**2<(a[0]-x)**2+(a[1]-z)**2?b:a);nnSum+=(nearest[2]-t)**2;
 }
 Object.assign(run.result,{unique_gradient_bins_0_1m:gradientBins.size,gradient_bins_per_m:gradientBins.size/run.result.travel_m,supported_fraction:count/640,supported_rmse:count?Math.sqrt(sum/count):null,gradient_supported_fraction:gradTotal?gradCount/gradTotal:null,gradient_supported_rmse:gradCount?Math.sqrt(gradSum/gradCount):null,full_grid_nearest_rmse:Math.sqrt(nnSum/640)});
}
await fs.writeFile(new URL('../output/experiments/exploration_comparison.json',import.meta.url),JSON.stringify(runs.map(r=>r.result),null,2)+'\n');
console.log(runs.filter(r=>['patch','tilted'].includes(r.result.field)).map(r=>r.result));
