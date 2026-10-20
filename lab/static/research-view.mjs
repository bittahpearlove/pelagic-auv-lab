export function setupResearch({request,config,download,canvas,line}) {
 const $=id=>document.getElementById(id);let result=null,busy=false;
 const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
 const fmt=(v,k=1)=>v===null||!Number.isFinite(v)?'—':(v*k).toFixed(2);
 function plot(){
  if(!result)return;const mode=$('research-diagnostic').value,rows=result.preview.filter(r=>r.mode===mode);
  const[c,w,h]=canvas('research-diagnostics');if(!w||!rows.length)return;
  const end=Math.max(...rows.map(r=>r.ms))/1000,X=t=>45+t/end*(w-65);
  c.font='10px system-ui';
  const panels=[{top:20,height:65,keys:[['estimated_gradient_cpm','#8ce4c4'],['fit_residual_c','#eab878']],label:'Gradient °C/m / residual °C'},
   {top:115,height:60,keys:[['speed_limit_mps','#8ce4c4'],['true_vertical_mps','#78baf5']],label:'Requested / achieved speed m/s'},
   {top:205,height:60,keys:[['fit_valid','#8ce4c4'],['policy_reason','#eab878']],label:'Reliability 0/1 / reason 0–7'}];
  for(const p of panels){const values=rows.flatMap(r=>p.keys.map(([k])=>r[k])).filter(Number.isFinite),lo=Math.min(0,...values),hi=Math.max(.01,...values);const Y=v=>p.top+p.height-(v-lo)/(hi-lo)*p.height;
   c.fillStyle='#97aebb';c.fillText(p.label,5,p.top-7);c.fillText(fmt(hi),5,p.top+8);c.fillText(fmt(lo),5,p.top+p.height);c.strokeStyle='#35454f';c.strokeRect(45,p.top,w-65,p.height);
   for(const[k,color]of p.keys)line(c,rows.map(r=>[X(r.ms/1000),Y(r[k])]),color);
  }c.fillStyle='#97aebb';c.fillText('0 s',45,h-10);c.fillText(end.toFixed(0)+' s',w-45,h-10);
 }
 function render(){
  if(!result)return;const recon=$('research-reconstruction').value,body=$('research-results');body.replaceChildren();
  for(const mode of ['adaptive','fast','slow','medium','response','ungated'])for(const leg of ['descent','ascent']){
   const ms=result.metrics.filter(r=>r.mode===mode&&r.direction===leg&&r.reconstruction===recon),trials=result.trials.filter(r=>r.mode===mode);if(!ms.length)continue;
   const avg=k=>mean(ms.map(r=>r[k]).filter(v=>v!==null)),expected=ms.filter(r=>r.boundary_expected);
   const values=[(mode==='adaptive'?'legacy adaptive':mode)+' / '+leg,fmt(avg('full_profile_rmse_c'))+' / '+fmt(avg('covered_profile_rmse_c')),fmt(avg('transition_rmse_c')),fmt(avg('boundary_depth_error_m'),100),fmt(avg('coverage'),100),expected.filter(r=>r.boundary_failed).length+'/'+expected.length,fmt(mean(trials.map(r=>r.elapsed_s)))];
   const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);
  }
  const ts=result.trials;$('research-status').textContent=`${ts.filter(r=>r.full_profile_complete).length}/${ts.length} full profiles · ${ts.filter(r=>r.complete).length} surfaced · ${ts.filter(r=>r.censored).length} censored · ${ts.filter(r=>r.faults).length} faults. ${result.repeats} scenarios. RMSE means omit unavailable values; consult coverage and failures. Saved: ${result.run_directory}. Simulation evidence only.`;
  $('research-paired').replaceChildren(...result.paired.map(e=>{const p=document.createElement('p');p.textContent=`${e.contrast} / ${e.direction}: conditional Δ ${fmt(e.conditional_mean_difference_m,100)} cm; 95% interval ${e.conditional_bootstrap_95_m?e.conditional_bootstrap_95_m.map(v=>fmt(v,100)).join(' to '):'unavailable'}; joint detections ${e.joint_valid_pairs}/${e.expected_boundary_pairs}, failures method/baseline ${e.method_failures}/${e.baseline_failures}${e.exploratory?' · exploratory small sample':''}. Negative favours response.`;return p;}));
  $('research-export').disabled=false;plot();
 }
 $('research-run').onclick=async()=>{if(busy)return;busy=true;$('research-run').disabled=true;$('research-status').textContent='Running six matched methods and saving an immutable development experiment…';
  try{await request('/api/action',{action:'research',...config(),shape:$('thermal-shape').value,repeats:Number($('research-count').value),varied:$('research-varied').checked});result=await(await request('/api/research')).json();$('research-diagnostic').replaceChildren(...[...new Set(result.preview.map(r=>r.mode))].map(name=>{const o=document.createElement('option');o.value=name;o.textContent=name;return o;}));$('research-diagnostic').value='response';render();}
  catch(e){$('research-status').textContent=e.message;}finally{busy=false;$('research-run').disabled=false;}};
 $('research-reconstruction').onchange=render;$('research-diagnostic').onchange=plot;window.addEventListener('resize',plot);
 $('research-export').onclick=async()=>{try{download(await(await request('/api/research.csv')).blob(),'pelagic-profile-trials.csv');}catch(e){$('research-status').textContent=e.message;}};
}
