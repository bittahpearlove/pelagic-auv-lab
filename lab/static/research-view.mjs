import {fitStatuses,selectedReconstruction,summarize,depthStatuses,flatMissionCounts} from '/research-summary.mjs';
export function setupResearch({request,config,download,canvas,line}) {
 const $=id=>document.getElementById(id);let result=null,busy=false;
 const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
 const fmt=(v,k=1)=>v===null||!Number.isFinite(v)?'—':(v*k).toFixed(2);
 function plot(){
  if(!result)return;const mode=$('research-diagnostic').value,rows=result.preview.filter(r=>r.mode===mode);
  const[c,w,h]=canvas('research-diagnostics');if(!w||!rows.length)return;
  const end=Math.max(...rows.map(r=>r.ms))/1000,X=t=>45+t/end*(w-65);
  c.font='10px system-ui';
  const panels=[{top:20,height:50,keys:[['estimated_gradient_cpm','#8ce4c4']],label:'Signed gradient °C/m'},
   {top:110,height:45,keys:[['fit_residual_c','#eab878']],label:'Forward-fit residual °C'},
   {top:200,height:50,keys:[['speed_limit_mps','#8ce4c4'],['true_vertical_mps','#78baf5']],label:'Requested / achieved |vertical speed| m/s'},
   {top:290,height:50,keys:[['fit_valid','#8ce4c4'],['policy_reason','#eab878']],label:'Fit accepted (mint, 0/1) / decision reason (amber, 0–7)'}];
  const value=(r,k)=>k==='true_vertical_mps'?Math.abs(r[k]):r[k];
  for(const p of panels){const values=rows.flatMap(r=>p.keys.map(([k])=>value(r,k))).filter(Number.isFinite),lo=Math.min(0,...values),hi=Math.max(.01,...values);const Y=v=>p.top+p.height-(v-lo)/(hi-lo)*p.height;
   c.fillStyle='#97aebb';c.fillText(p.label,5,p.top-7);c.fillText(fmt(hi),5,p.top+8);c.fillText(fmt(lo),5,p.top+p.height);c.strokeStyle='#35454f';c.strokeRect(45,p.top,w-65,p.height);
   for(const[k,color]of p.keys)line(c,rows.map(r=>[X(r.ms/1000),Y(value(r,k))]),color);
  }c.fillStyle='#97aebb';c.fillText('0 s',45,h-10);c.fillText(end.toFixed(0)+' s',w-45,h-10);
 }
 function render(){
  if(!result)return;const recon=$('research-reconstruction').value,body=$('research-results');body.replaceChildren();
  for(const mode of ['adaptive','fast','slow','medium','response','ungated'])for(const leg of ['descent','ascent']){
   const ms=result.metrics.filter(r=>r.mode===mode&&r.direction===leg&&r.reconstruction===selectedReconstruction(mode,recon)),trials=result.trials.filter(r=>r.mode===mode);if(!ms.length)continue;
   const summary=summarize(ms),avg=summary.avg,expected=ms.filter(r=>r.boundary_expected);
   const values=[(mode==='adaptive'?'legacy adaptive':mode)+' / '+leg,fmt(avg('full_profile_rmse_c'))+` (${summary.fullAvailable}/${ms.length}) / `+fmt(avg('covered_profile_rmse_c')),fmt(avg('transition_rmse_c')),fmt(avg('boundary_depth_error_m'),100),fmt(avg('boundary_loss_m'),100),fmt(avg('coverage'),100),expected.filter(r=>r.boundary_failed).length+'/'+expected.length,fmt(mean(trials.map(r=>r.elapsed_s)))];
   const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);
  }
  const ts=result.trials;$('research-status').textContent=`${ts.filter(r=>r.full_profile_complete).length}/${ts.length} full profiles · ${ts.filter(r=>r.complete).length} surfaced · ${ts.filter(r=>r.censored).length} censored · ${ts.filter(r=>r.faults).length} faults. ${result.repeats} scenarios. RMSE means omit unavailable values; consult coverage and failures. Saved run: ${result.run_directory?.split('/').at(-1)||'in memory'}. Simulation evidence only.`;
  $('research-paired').replaceChildren(...result.paired.map(e=>{const p=document.createElement('p');p.textContent=`${e.contrast} / ${e.direction}: all-expected-boundary loss Δ ${fmt(e.failure_aware_mean_difference_m,100)} cm (${e.failure_aware_pairs} pairs); loss 95% interval ${e.failure_aware_bootstrap_95_m?e.failure_aware_bootstrap_95_m.map(v=>fmt(v,100)).join(' to '):'unavailable'} cm; conditional error Δ ${fmt(e.conditional_mean_difference_m,100)} cm; 95% interval ${e.conditional_bootstrap_95_m?e.conditional_bootstrap_95_m.map(v=>fmt(v,100)).join(' to '):'unavailable'}; joint detections ${e.joint_valid_pairs}/${e.expected_boundary_pairs}, failures method/baseline ${e.method_failures}/${e.baseline_failures}${e.exploratory?' · exploratory small sample':''}. Negative favours response.`;return p;}));
  const actualTaus=[...new Set(result.manifest.scenarios.map(s=>s.true_tau_s))].sort((a,b)=>a-b);$('research-saved-settings').textContent=`Displayed run: ${result.repeats} scenarios, seed ${result.seed}; ${actualTaus.length>1?'varied scenario fields':`layer ${result.params.center} m, ${Math.round(result.params.width*100)} cm scale, noise σ ${result.params.noise} °C`}; actual lag ${actualTaus.length>1?'varied '+actualTaus.join(', '):actualTaus[0]} s; miss penalty ${result.policy.boundary_miss_penalty_m??.3} m. These are the saved run settings.`;renderOverview();renderRejections();$('research-export').disabled=false;plot();
 }

 function renderOverview(){
  if(!result)return;const container=$('research-overview');container.replaceChildren();const direction=$('overview-leg').value;
  for(const [label,mode,recon] of [['Response-aware / forward','response','forward'],['Fixed medium / raw','medium','raw']]){
   const ms=result.metrics.filter(m=>m.mode===mode&&m.reconstruction===recon&&m.direction===direction),v=summarize(ms),a=document.createElement('article');
   const title=document.createElement('span');title.textContent=label;
   const count=document.createElement('strong');count.textContent=v.expected?`${v.detected}/${v.expected} boundary detections`:'No expected boundary';
   const detail=document.createElement('p');detail.textContent=`${v.missed} missed; mean failure-aware loss ${fmt(v.avg('boundary_loss_m'),100)} cm. ${direction} only. Separate scenario pairs are used for comparison.`;
   a.append(title,count,detail);container.append(a);
  }
  const flats=flatMissionCounts(result.metrics.filter(m=>m.reconstruction===selectedReconstruction(m.mode,$('research-reconstruction').value)));
  const a=document.createElement('article'),title=document.createElement('strong'),p=document.createElement('p');title.textContent='Check complete data';p.textContent=`${result.trials.filter(t=>t.full_profile_complete).length}/${result.trials.length} full missions. Full RMSE cells show available/total profiles. Missing never means zero error. Flat-water false-positive missions: ${flats.falsePositiveMissions}/${flats.missions}, using the selected reconstructions. Headline detection cards always show response/fit versus medium/raw.`;a.append(title,p);container.append(a);
 }
 function renderRejections(){
  if(!result)return;const container=$('research-rejections'),mode=$('research-diagnostic').value;container.replaceChildren();
  const key=document.createElement('div');key.className='status-key';
  for(const[name,label,color]of fitStatuses){const item=document.createElement('span');item.textContent=label;item.style.setProperty('--status-color',color);key.append(item);}container.append(key);
  for(const direction of ['descent','ascent']){
   const ms=result.metrics.filter(m=>m.mode===mode&&m.direction===direction&&m.reconstruction==='raw');
   const row=document.createElement('div');row.className='status-row';const label=document.createElement('strong');label.textContent=`${mode} / ${direction} · depth 0.10 → 0.90 m`;
   const strip=document.createElement('div');strip.className='status-strip';
   for(const bin of depthStatuses(ms)){
    const cell=document.createElement('span'),dominant=fitStatuses.reduce((a,b)=>(bin.counts[b[0]]||0)>(bin.counts[a[0]]||0)?b:a);
    cell.style.background=bin.samples?dominant[2]:'#35454f';cell.title=`${bin.depth_m.toFixed(3)} m; ${bin.samples} fresh readings; `+fitStatuses.map(([k,l])=>`${l}: ${bin.counts[k]||0}`).join(', ');strip.append(cell);
   }
   const detail=document.createElement('p'),total=ms.reduce((n,m)=>n+m.transition_status_samples,0);
   detail.textContent=total?`Within reference transition (${total} fresh readings): `+fitStatuses.map(([name,label])=>`${label} ${(100*ms.reduce((n,m)=>n+(m.transition_status_counts?.[name]||0),0)/total).toFixed(1)}%`).join(' · '):'No fresh readings inside an expected transition. This includes flat-water scenarios; inspect coverage and failures.';
   row.append(label,strip,detail);container.append(row);
  }
 }
 function acceptResult(saved){result=saved;$('research-diagnostic').replaceChildren(...[...new Set(result.preview.map(r=>r.mode))].map(name=>{const o=document.createElement('option');o.value=name;o.textContent=name;return o;}));$('research-diagnostic').value='response';render();}
 function configSummary(){const p=config();$('research-config-summary').textContent=`Layer at ${p.center.toFixed(2)} m, ${(p.width*100).toFixed(0)} cm scale, ${p.drop.toFixed(1)} °C drop · noise σ ${p.noise.toFixed(3)} °C · actual lag ${p.tau.toFixed(1)} s · assumed lag ${p.research_policy.tau_nominal_s.toFixed(1)} s · loss cap ${(p.research_policy.boundary_error_cap_m*100).toFixed(0)} cm / miss penalty ${(p.research_policy.boundary_miss_penalty_m*100).toFixed(0)} cm · seed ${p.seed}. ${$('research-varied').checked?'Varied conditions override the nominal water preset. ':''}Changes apply to the next comparison; saved results keep their original settings.`;}
 document.addEventListener('lab-view-changed',event=>{if(event.detail==='research')requestAnimationFrame(plot);});
 document.querySelectorAll('input,select').forEach(el=>el.addEventListener('change',configSummary));configSummary();

 $('research-run').onclick=async()=>{if(busy)return;busy=true;$('research-run').disabled=true;$('research-status').textContent='Running six matched methods and saving an immutable development experiment…';
  try{await request('/api/action',{action:'research',...config(),shape:$('thermal-shape').value,repeats:Number($('research-count').value),varied:$('research-varied').checked});acceptResult(await(await request('/api/research')).json());}
  catch(e){$('research-status').textContent=e.message;}finally{busy=false;$('research-run').disabled=false;}};
 $('research-diagnostic-panel').addEventListener('toggle',()=>{if($('research-diagnostic-panel').open){plot();renderRejections();}});$('overview-leg').onchange=renderOverview;$('research-reconstruction').onchange=render;$('research-diagnostic').onchange=()=>{plot();renderRejections();};window.addEventListener('resize',plot);
 (async()=>{try{const saved=await(await request('/api/research')).json();if(!busy&&saved.metrics)acceptResult(saved);}catch{/* The next comparison can still run if no saved result is available. */}})();
 $('research-export').onclick=async()=>{try{download(await(await request('/api/research.csv')).blob(),'pelagic-profile-trials.csv');}catch(e){$('research-status').textContent=e.message;}};
}
