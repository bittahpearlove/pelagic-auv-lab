// Presentation-only aggregation; never changes policy decisions or stored scores.
export const fitStatuses=[['good','Accepted','#8ce4c4'],['warming','Warming up','#78baf5'],['geometry','Insufficient depth support','#eab878'],['conditioning','Ill-conditioned fit','#bda0ea'],['residual_or_proxy','Residual / proxy rejected','#ed9393'],['stale','Stale','#e6dc87'],['input','Invalid input','#f38bc3']];
export function selectedReconstruction(mode,selection){return selection==='primary'?(mode==='response'||mode==='ungated'?'forward':'raw'):selection;}
export function summarize(metrics){
 const expected=metrics.filter(m=>m.boundary_expected),detected=expected.filter(m=>m.boundary_depth_error_m!==null);
 const avg=key=>{const values=metrics.map(m=>m[key]).filter(Number.isFinite);return values.length?values.reduce((a,b)=>a+b,0)/values.length:null;};
 return {expected:expected.length,detected:detected.length,missed:expected.length-detected.length,fullAvailable:metrics.filter(m=>Number.isFinite(m.full_profile_rmse_c)).length,avg};
}
export function depthStatuses(metrics){
 const result=[];
 for(const metric of metrics) for(const bin of metric.status_by_depth||[]){
  let target=result.find(b=>Math.abs(b.depth_m-bin.depth_m)<1e-6);
  if(!target){target={depth_m:bin.depth_m,samples:0,counts:{}};result.push(target);}
  target.samples+=bin.samples;for(const [key,n]of Object.entries(bin.counts))target.counts[key]=(target.counts[key]||0)+n;
 }
 return result.sort((a,b)=>a.depth_m-b.depth_m);
}
export function flatMissionCounts(metrics){
 const groups=new Map();
 for(const m of metrics)if(!m.boundary_expected){const key=m.scenario_id+'/'+m.mode;groups.set(key,(groups.get(key)||false)||m.false_boundary_peaks>0);}
 return {missions:groups.size,falsePositiveMissions:[...groups.values()].filter(Boolean).length};
}
