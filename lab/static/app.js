'use strict';
import {MovementDemo,generateSurvey} from '/demo-model.mjs';
import {SurveyPlanner,surveyControls} from '/survey-planner.mjs';
import {KeyboardDrive} from '/keyboard.mjs';
import {ThermalMap,temperatureAt,trueGradient} from '/thermal-map.mjs';
const $=id=>document.getElementById(id), token=document.querySelector('meta[name="lab-token"]').content;
let snapshot=null, rows=[], seq=0, busy=false, message='', lastSource='offline', actionQueue=Promise.resolve();
let activity='profile',swim=new MovementDemo(),swimRunning=false,swimPaused=false,swimRows=[],visualX=2,visualVx=0,trail=[],previousFrame=0,accumulator=0;
const drive=new Set(),keyboard=new KeyboardDrive(),pointerDrive=new Map();
let consoleRows=[],consoleSeq=0,consoleRevision='';
let autoPlanner=null;
const freeMap=new ThermalMap(),profileMap=new ThermalMap();let thermalMap=profileMap,mapCache=null,mapUpdated=0,surveyMessage='Explore with WASD, or generate a labelled simulated survey.';
function clearDrive(){drive.clear();keyboard.clear();pointerDrive.clear();renderKeys();}
function syncDrive(){if(keyboard.directions().size||pointerDrive.size)cancelSurvey('Manual steering override');drive.clear();for(const direction of [...keyboard.directions(),...pointerDrive.values()])drive.add(direction);renderKeys();}
const shapeNames=['layer','tilted','front','patch','combined'];
function profileX(){if(activity==='explore')return snapshot?.latest?.x_m??Number($('profile-x').value);return snapshot?.source==='nano'?(snapshot.firmware_config?.profile_x_m??4):Number($('profile-x').value);}
function water(){const c=snapshot?.firmware_config;if(snapshot?.source==='nano'&&activity!=='explore')return {center:c?.water_center_m??.5,width:c?.water_width_m??.07,drop:c?.water_drop_c??3,tau:c?.probe_tau_s??2,noise:0,profile_x:profileX(),shape:shapeNames[c?.water_shape??0]};return {...config(),shape:$('thermal-shape').value};}
function applyParams(p){for(const k of ['center','width','drop','tau','noise'])if(p[k]!==undefined)$(k).value=p[k];if(p.profile_x!==undefined)$('profile-x').value=p.profile_x;if(p.shape!==undefined)$('thermal-shape').value=p.shape;labels();}
function setView(name){clearDrive();document.body.dataset.view=name;document.querySelectorAll('.view-tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===name)));requestAnimationFrame(draw);}
document.querySelectorAll('.view-tabs button').forEach(b=>b.onclick=()=>setView(b.dataset.view));
$('map-jump').onclick=e=>{e.preventDefault();setView('maps');};document.querySelector('.intro-actions a[href="#lab-console"]').onclick=e=>{e.preventDefault();setView('console');};
function view(){if(activity==='explore'&&!snapshot?.exploring)return snapshot?{...snapshot,latest:null}:null;if(activity!=='swim')return snapshot;const r={ms:swim.t*1000,depth_m:swim.z,temperature_c:swim.measured,true_temperature_c:swim.truth,vertical_mps:swim.vz,target_depth_m:swim.z,state:0,energy_j:0};return {...snapshot,source:'offline',running:swimRunning,paused:swimPaused,latest:r,events:[{time:swim.t,text:'Browser free swim · no Nano steering'}]};}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function renderSettings(){const c=snapshot?.firmware_config||{};$('config-origin').textContent=Object.keys(c).length?'Read from '+snapshot.config_source+' · read-only'+(activity!=='profile'?' · profile controller only':''):'No settings received. Connect the Nano running v0.5 (v0.4 supports read-only settings).';const fields=[['Field shape (0–4)','water_shape',''],['Profile x','profile_x_m','m'],['Target depth','target_depth_m','m'],['Depth limit','max_depth_m','m'],['Normal rate','normal_speed_mps','m/s'],['Slow rate','slow_speed_mps','m/s'],['Assumed probe τ','probe_tau_s','s'],['Allowed lag','allowed_lag_m','m'],['Gradient window','gradient_window_m','m'],['Enter gradient','gradient_enter_cpm','°C/m'],['Exit gradient','gradient_exit_cpm','°C/m'],['Control interval','control_ms','ms'],['Telemetry interval','telemetry_ms','ms'],['Mission limit','mission_timeout_ms','ms'],['Water layer centre','water_center_m','m'],['Water layer scale','water_width_m','m'],['Water temperature drop','water_drop_c','°C']];$('config-values').replaceChildren(...fields.filter(([,key])=>key in c).map(([label,key,unit])=>{const row=document.createElement('div');row.className='config-row';const name=document.createElement('span');name.textContent=label;const value=document.createElement('strong');value.textContent=Number(c[key].toFixed(4))+' '+unit;row.append(name,value);return row;}));}
function changeActivity(next){if(next==='explore'&&activity!==next){rows=[];seq=0;profileMap.clear();}if(next==='explore')$('noise').value=0;cancelSurvey('Activity changed');activity=next;thermalMap=next==='swim'?freeMap:profileMap;if(next==='swim')swim.truth=temperatureAt(swim.x,swim.z,water());mapCache=null;clearDrive();}
function resetSwim(){autoPlanner=null;swim.reset();swim.truth=temperatureAt(swim.x,swim.z,water());swimRows=[];swimRunning=false;swimPaused=false;freeMap.clear();mapCache=null;surveyMessage='Explore with WASD, or generate a labelled simulated survey.';}
function addMapSample(){const row=swim.rows.at(-1);if(row)thermalMap.add(row[1],row[2],row[6]);}
function updateSwimRows(){swimRows=swim.rows.map(r=>({ms:r[0]*1000,depth_m:r[2],temperature_c:r[6],true_temperature_c:r[5],target_depth_m:r[2]}));}
function saveExploreField(){return act('explore_field',{...config(),shape:$('thermal-shape').value});}
async function selectField(event){
 if(activity==='swim'){resetSwim();render();return;}
 if(activity==='explore'){
  // Every dropdown structure includes a contrast term. The isolated-spot preset
  // alone deliberately sets it to zero; choosing a structure restores it.
  if(event?.target.id==='thermal-shape'&&Number($('drop').value)===0)applyParams({drop:3});
  await saveExploreField();return;
 }
 await act('field',{shape:$('thermal-shape').value,profile_x:Number($('profile-x').value)});
}
$('thermal-shape').onchange=selectField;$('profile-x').onchange=selectField;$('profile-x').oninput=labels;
function surveyOptions(){
 const fields=['survey-spacing','survey-goal','survey-threshold','survey-budget'];
 if(fields.some(id=>!$(id).checkValidity())){fields.forEach(id=>$(id).reportValidity());return null;}
 return {policy:$('survey-policy').value,spacing:Number($('survey-spacing').value),targetCoverage:Number($('survey-goal').value)/100,threshold:Number($('survey-threshold').value),budget:Number($('survey-budget').value)};
}
function cancelSurvey(reason){if(autoPlanner){autoPlanner.finish(reason);swim.survey=autoPlanner.report();autoPlanner=null;surveyMessage='Survey interrupted: '+reason+'.';}}
function surveySummary(){const r=autoPlanner?.report()||swim.survey;if(!r)return 'No planned survey yet.';return `${r.policy} · ${(r.coverage*100).toFixed(1)}% near-track coverage / ${(r.targetCoverage*100).toFixed(0)}% goal · ${r.seconds.toFixed(1)} s / ${r.budget} s · ${r.distance.toFixed(1)} m · ${r.refinements} local passes started · ${r.reason||r.phase}. Coverage is geometric; temperature accuracy is separate.`;}
$('warm-spot').onclick=()=>{if(activity!=='swim'||swimRunning)return;applyParams({shape:'patch',drop:0,center:1.3});resetSwim();surveyMessage='Isolated warm spot: 22 °C background, up to 24 °C patch. Its location is hidden from the planner.';render();};
$('survey-export').onclick=()=>download(new Blob([JSON.stringify({source:'browser_simulation',plane:'length-depth',water:water(),planner:autoPlanner?.report()||swim.survey},null,2)],{type:'application/json'}),'pelagic-survey-report.json');
$('survey-route').onchange=draw;
$('explore-spot').onclick=async()=>{if(snapshot?.running)return;applyParams({shape:'patch',drop:0,center:1.3,noise:0});await saveExploreField();};
$('explore-layers').onclick=async()=>{if(snapshot?.running)return;applyParams({shape:'tilted',drop:3,center:1.3,width:.1,noise:0});await saveExploreField();};
$('map-export').onclick=()=>{
 drawMaps();const p=water(),header='source,shape,center_m,width_m,drop_c,probe_tau_s,x_m,depth_m,estimate_c,reference_c,gradient_x_cpm,gradient_depth_cpm,support_heuristic';
 const lines=mapCache.nodes.map(n=>[activity==='swim'?'browser_simulation':snapshot?.source==='nano'?(activity==='explore'?'nano_in_loop_lab_water':'nano_simulation'):'native_simulation',p.shape,p.center,p.width,p.drop,p.tau,n.x,n.z,n.estimate?.temperature??'',n.truth,n.estimate?.gradient?.gx??'',n.estimate?.gradient?.gz??'',n.estimate?.coverage??0].join(','));
 download(new Blob([header+'\n'+lines.join('\n')+'\n'],{type:'text/csv'}),'pelagic-simulated-thermal-map.csv');
};
for(const id of ['map-display','map-arrows','map-boundary'])$(id).onchange=()=>{mapCache=null;drawMaps();};
$('activity').onchange=async()=>{const desired=$('activity').value;clearDrive();if(snapshot?.running){$('activity').value=activity;return;}if(desired==='swim'&&snapshot?.source==='nano'){await act('source',{value:'offline'});if(message){$('activity').value=activity;return;}}if(activity==='explore'&&desired!=='explore'&&snapshot?.exploring)await act('reset');changeActivity(desired);swimRunning=false;swimPaused=false;render();};
$('drive-stop').onclick=()=>{cancelSurvey('Coast requested');clearDrive();};
function editing(target){return target instanceof Element&&Boolean(target.closest('input,select,textarea,[contenteditable="true"],[role="textbox"]'));}
window.addEventListener('keydown',e=>{
 if(e.ctrlKey||e.metaKey||e.altKey||e.isComposing||editing(e.target))return;
 if(activity!=='swim')return;
 if(keyboard.press(e.code,e.repeat)){e.preventDefault();syncDrive();return;}
 if(activity!=='swim')return;
 if(e.code==='Space'){if(e.target instanceof Element&&e.target.closest('button'))return;e.preventDefault();cancelSurvey('Coast requested');clearDrive();}
 const shortcuts={KeyP:'pause',Escape:'stop',KeyR:'reset',Enter:'start'};
 if(shortcuts[e.code]&&!e.repeat){if(e.code==='Enter'&&e.target instanceof Element&&e.target.closest('button'))return;e.preventDefault();const button=$(shortcuts[e.code]);if(!button.disabled)button.click();}
});
window.addEventListener('keyup',e=>{keyboard.release(e.code);syncDrive();});window.addEventListener('blur',clearDrive);document.addEventListener('visibilitychange',()=>{if(document.hidden)clearDrive();});document.addEventListener('focusin',e=>{if(editing(e.target))clearDrive();});$('tank').addEventListener('blur',()=>{if(activity!=='swim')clearDrive();});
document.querySelectorAll('[data-drive]').forEach(b=>{b.onpointerdown=e=>{if(b.disabled)return;e.preventDefault();b.setPointerCapture(e.pointerId);pointerDrive.set(e.pointerId,b.dataset.drive);syncDrive();};for(const type of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(type,e=>{pointerDrive.delete(e.pointerId);syncDrive();});});
function renderKeys(){document.querySelectorAll('[data-key]').forEach(el=>el.classList.toggle('held',drive.has(el.dataset.key)));$('keyboard-status').textContent=drive.size?'Input: '+[...drive].join(' + '):'Keyboard ready · no movement keys held';}
function consoleText(entry){return `${entry.time} [${entry.origin}] ${entry.text}`;}
function renderConsole(){
 $('console-refresh').disabled=snapshot?.source!=='nano'||!snapshot?.verified;$('console-export').disabled=!consoleRows.length;
 const filter=$('console-filter').value,telemetry=$('console-telemetry').checked;
 const visible=consoleRows.filter(e=>(filter==='all'||e.origin===filter)&&(telemetry||e.kind!=='telemetry'));
 $('console-count').textContent=visible.length+' shown / '+consoleRows.length+' retained';
 const revision=[consoleRows.at(-1)?.id||0,consoleRows.length,filter,telemetry].join(':');if(revision===consoleRevision)return;consoleRevision=revision;
 const output=$('console-output'),scroll=output.scrollTop;output.textContent=visible.map(consoleText).join('\n')||'No messages match this view.';
 output.scrollTop=$('console-follow').checked?output.scrollHeight:scroll;
}
$('console-filter').onchange=renderConsole;$('console-telemetry').onchange=renderConsole;$('console-follow').onchange=()=>{if($('console-follow').checked)$('console-output').scrollTop=$('console-output').scrollHeight;};
$('console-clear').onclick=()=>{consoleRows=[];consoleRevision='';renderConsole();};
$('console-export').onclick=()=>download(new Blob([consoleRows.map(consoleText).join('\n')+'\n'],{type:'text/plain'}),'pelagic-laboratory.log');
$('console-refresh').onclick=()=>act('diagnostics');
function frame(now){const elapsed=Math.min(.1,previousFrame?(now-previousFrame)/1000:0);previousFrame=now;accumulator+=document.hidden?0:elapsed;const surge=Number(drive.has('right'))-Number(drive.has('left')),heave=Number(drive.has('down'))-Number(drive.has('up'));while(accumulator>=.02){accumulator-=.02;if(activity==='swim'&&swimRunning&&!swimPaused){let controls={surge,heave};if(autoPlanner){const target=autoPlanner.update(swim);if(!target){swim.survey=autoPlanner.report();autoPlanner=null;swimRunning=false;surveyMessage=surveySummary();render();continue;}controls=surveyControls(swim,target);}const before=swim.rows.at(-1);swim.step(.02,controls.surge,controls.heave,water().tau,water());if(swim.rows.at(-1)!==before){updateSwimRows();addMapSample();if(autoPlanner){const r=swim.rows.at(-1);autoPlanner.observe({x:r[1],z:r[2],temperature:r[6],t:r[0]});}}}else if(activity==='profile'){visualX=profileX();visualVx=0;}}if(activity==='profile'&&snapshot?.latest){trail.push([visualX,snapshot.latest.depth_m]);if(trail.length>2000)trail.shift();}drawTank();requestAnimationFrame(frame);}
const states=['Disarmed','Arming','Descending','Depth hold','Ascending','Complete','Fault'];
const faultNames=[[1,'Invalid sensor'],[2,'Stale sensor'],[4,'Leak'],[8,'Low battery'],[16,'Overcurrent'],[32,'Excess tilt'],[64,'Depth envelope'],[128,'Mission timeout'],[256,'Arm removed'],[512,'Operator stop']];
async function request(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:{'X-Lab-Token':token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});if(!response.ok){let data=await response.json();throw Error(data.error||'Request failed')}return response;}
function act(action,extra={}){const run=async()=>{busy=true;try{await request('/api/action',{action,...extra});message='';if(['reset','source','start','field','explore_field','explore_start'].includes(action)){rows=[];seq=0;trail=[];visualX=profileX();visualVx=0;profileMap.clear();mapCache=null;}await poll();}catch(e){message=e.message;render();}finally{busy=false;}};actionQueue=actionQueue.then(run,run);return actionQueue;}
function config(){return {...Object.fromEntries(['center','width','drop','tau','noise'].map(k=>[k,Number($(k).value)])),profile_x:Number($('profile-x').value)};}
function labels(){const c=config();$('center-out').textContent=c.center.toFixed(2)+' m';$('drop-out').textContent=c.drop.toFixed(1)+' °C';$('width-out').textContent=Math.round(c.width*100)+' cm';$('tau-out').textContent=c.tau.toFixed(1)+' s';$('noise-out').textContent=c.noise.toFixed(3)+' °C';$('profile-x-out').textContent=c.profile_x.toFixed(2)+' m';}
$('source').onchange=async()=>{clearDrive();swimRunning=false;changeActivity(activity==='explore'?'explore':'profile');$('activity').value=activity;await act('source',{value:$('source').value});if(activity==='explore')await saveExploreField();};$('connect').onclick=()=>act(snapshot?.connected?'disconnect':'connect');
$('mode').onchange=()=>act('mode',{value:Number($('mode').value)});$('speed').onchange=()=>act('speed',{value:Number($('speed').value)});
$('start').onclick=async()=>{if(activity==='explore'){await act('explore_start',{...config(),shape:$('thermal-shape').value,adaptive:true});return;}if(activity==='swim'){if(swim.survey)resetSwim();swimRunning=true;swimPaused=false;render();return;}if(snapshot?.source==='offline'){await act('configure',{...config(),shape:$('thermal-shape').value,mode:Number($('mode').value)});if(message)return;}await act('start');};
$('quick-run').onclick=()=>$('start').click();
$('pause').onclick=()=>{if(activity==='swim'){swimPaused=!swimPaused;render();}else act('pause');};$('reset').onclick=async()=>{clearDrive();if(activity==='swim'){resetSwim();render();}else{visualX=2;visualVx=0;trail=[];if(activity==='explore'){if(snapshot?.running)await act('stop');await saveExploreField();}else act('reset');}};$('stop').onclick=()=>{clearDrive();if(activity==='swim'){cancelSurvey('Operator stop');swimRunning=false;swimPaused=false;render();}else act('stop');};
document.querySelectorAll('[data-fault]').forEach(b=>b.onclick=()=>act('fault',{value:b.dataset.fault}));
['center','width','drop','tau','noise'].forEach(k=>{$(k).onchange=()=>{if(activity==='explore')saveExploreField();};$(k).oninput=()=>{if(activity==='swim')resetSwim();else{profileMap.clear();rows=[];seq=0;}labels();mapCache=null;draw();};});
function surveyCsv(){const r=autoPlanner?.report()||swim.survey;return r?[r.policy,r.spacing,r.targetCoverage,r.coverage,r.budget,r.reason||r.phase]:['manual','','','','',''];}
$('export').onclick=async()=>{if(activity==='swim'){download(new Blob(['time_s,x_m,depth_m,vx_mps,vz_mps,true_temperature_c,probe_temperature_c,surge,heave,source,field_shape,center_m,width_m,drop_c,probe_tau_s,survey_policy,track_spacing_m,coverage_goal,near_track_coverage,time_budget_s,stop_reason\n'+swim.rows.map(r=>[...r,'browser_simulation',water().shape,water().center,water().width,water().drop,water().tau,...surveyCsv()].join(',')).join('\n')],{type:'text/csv'}),'pelagic-free-swim.csv');return;}try{const response=await request('/api/export');const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='pelagic-'+(snapshot?.source||'offline')+'-run.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){message=e.message;render();}};
async function poll(){try{const d=await(await request('/api/state?since='+seq+'&console_since='+consoleSeq)).json();if(d.exploring&&activity!=='explore'){changeActivity('explore');applyParams(d.params);}if(d.source!==lastSource||d.seq<seq){rows=[];seq=0;profileMap.clear();mapCache=null;}if(d.source!==lastSource&&d.source==='offline'&&activity!=='explore'){applyParams(d.params);}lastSource=d.source;snapshot=d;if(d.console_seq<consoleSeq){consoleRows=[];consoleSeq=0;}for(const entry of d.console||[]){if(entry.id>consoleSeq){consoleRows.push(entry);consoleSeq=entry.id;}}if(consoleRows.length>500)consoleRows.splice(0,consoleRows.length-500);for(const row of d.rows){if(row.seq>seq){seq=row.seq;if(activity==='explore'&&!Number.isFinite(row.x_m))continue;rows.push(row);profileMap.add(row.profile_x_m??profileX(),row.depth_m,row.temperature_c);}}if(rows.length>10000)rows.splice(0,rows.length-10000);render();}catch(e){message='Local bridge unavailable. '+e.message;render();}}
function render(){if(!snapshot){$('notice').textContent=message||'Connecting to local lab…';return;}const d=view()||{},r=d.latest||{},offline=d.source==='offline',free=activity==='swim';const active=d.running;let note=activity==='explore'?(offline?'Native C++ exploration controller ↔ lab water and motion. Same controller header as Nano v0.14.':'Nano v0.14 ↔ lab water and motion over USB. The board decides motion; the lab supplies measured inputs. Motors disabled.'):free?'Free swim uses browser physics and your virtual water settings. No steering commands go to the Nano.':offline?'Offline mode runs the same C++ control logic as the Nano, inside a simplified virtual water column.':'Nano mode runs firmware on your board. Its water model is simulated; settings below do not change the device.';
document.querySelectorAll('.truth-key').forEach(el=>el.style.display=offline||activity==='explore'?'':'none');
if(d.stale)note='Nano telemetry is stale. The device may continue its simulated mission; reconnect to recover control.';
const faults=activity==='explore'?0:Number(r.faults||0);if(faults)note='Fault latched: '+faultNames.filter(([bit])=>faults&bit).map(([,name])=>name).join(', ')+'. Reset before the next run.';
$('notice').textContent=message||d.error||note;$('notice').classList.toggle('error',Boolean(message||d.error||d.stale||faults));
$('connection').textContent=offline?'Offline water / native C++ controller':d.verified?'Nano verified / USB telemetry':d.connected?'Nano connected / verifying…':'Nano disconnected';
if(!offline&&activity!=='explore'&&d.firmware_config?.water_center_m!==undefined){const p=water();applyParams(p);}$('source').value=d.source;$('mode').value=d.mode;$('mode').disabled=active;$('connect').classList.toggle('hidden',offline);$('connect').textContent=d.connected?'Disconnect Nano':'Connect Nano';
$('usb-status').classList.toggle('hidden',offline);$('usb-status').textContent=d.error|| (d.verified?('Connected: '+d.port+' · '+d.identity):(d.connected?'USB open. Requesting firmware identity…':'Connect the Nano, then click Connect Nano.'));
$('activity').disabled=d.running&&!free;$('activity').value=activity;$('activity-note').textContent=activity==='explore'?'Controller-driven 2D trajectories; local cross-probes use measured changes, not simulator truth.':free?'Use WASD / arrows anywhere on the page, outside form fields. Enter starts free swim.':'Fixed vertical line through the selected field. This detector estimates dT/depth, not a full 2D gradient.';
$('mode').disabled=active||activity!=='profile';$('speed').disabled=free||!offline;
$('water-hint').textContent=activity==='explore'?'The selected probe τ is supplied to the controller to limit local speed. Noise is off in this first hardware-in-the-loop experiment. Settings lock during a run.':free?'Probe response delay can shift or blur the estimated boundary. Change water settings before a run; changing them clears the map.':'The profile controller assumes τ = 2 s. Change the actual lag to test model mismatch. Water settings lock during a run.';document.body.dataset.activity=activity;$('map-jump').classList.remove('hidden');$('thermal-controls').classList.remove('hidden');$('thermal-mapping').classList.remove('hidden');$('shape-hint').textContent=$('thermal-shape').value==='front'?'Lateral front at x = 4 m. Its transition scale is 5 × the scale slider. Layer centre is unused.':'Depth increases downwards. Sloping layers change by 0.16 m per horizontal metre. The patch adds up to 2 °C.';if(activity==='explore')$('shape-hint').textContent+=' Layer contrast: '+Number($('drop').value).toFixed(1)+' °C'+(Number($('drop').value)===0?' (uniform background; layer disabled).':'.');$('thermal-shape').disabled=active||(activity!=='explore'&&!offline&&(!d.verified||d.stale||!/^v0\.(?:[5-9]|1[0-4])/.test(d.identity)));$('profile-x').disabled=active||free||(activity!=='explore'&&!offline&&(!d.verified||d.stale||!/^v0\.(?:[5-9]|1[0-4])/.test(d.identity)));document.querySelector('label[for="profile-x"]').firstChild.textContent=activity==='explore'?'Descent x ':'Profile x ';$('profile-slice-note').textContent=!offline&&!/^v0\.(?:[5-9]|1[0-4])/.test(d.identity)?'Reconnect and upload v0.5 for field selection. Older firmware uses its reported level layer.':'Vertical line at x='+profileX().toFixed(2)+' m; target 1.0 m. Only boundaries within the travelled depth range are crossed.';$('example-survey').disabled=active;for(const id of ['auto-survey','warm-spot','survey-policy','survey-spacing','survey-goal','survey-threshold','survey-budget'])$(id).disabled=active;$('survey-summary').textContent=surveySummary();$('survey-export').disabled=!swim.survey&&!autoPlanner;$('survey-note').textContent=surveyMessage;
$('environment').style.opacity=offline||activity==='explore'?'1':'.4';['center','drop','width','tau','noise'].forEach(k=>$(k).disabled=active||(!offline&&activity!=='explore')||((free||activity==='explore')&&k==='noise'));$('start').textContent=activity==='explore'?'▶ Run exploration':free?'▶ Start free swim':'▶ Run profile';$('quick-run').textContent=activity==='explore'?'▶ Explore':free?'▶ Swim':'▶ Profile';$('start').disabled=active||(!offline&&(!d.verified||d.stale||(activity==='explore'&&!d.identity.startsWith('v0.14'))));$('quick-run').disabled=$('start').disabled;$('pause').disabled=!active||!offline;$('pause').textContent=d.paused?'Resume':'Pause';$('speed').disabled=!offline||free;$('speed').value=free?1:d.speed;
document.querySelectorAll('[data-fault]').forEach(b=>b.disabled=!offline||!active||activity!=='profile');$('export').disabled=free?!swim.rows.length:!rows.length;
$('state').textContent=activity==='explore'?(active?(d.exploration?.mission_phase===8?'RETURNING TO DESCENT':d.exploration?.mission_phase===9?'ASCENDING TO SURFACE':d.exploration?.mission_phase===7?'RETURNING TO DESCENT':d.exploration?.mission_phase===6?'MOVING TO UNVISITED WATER':d.exploration?.mission_phase===5?'HOLD · MAX 8 SECONDS':d.exploration?.local?(d.exploration?.mission_phase===1?'SLOW UPWARD RETRACE':'LOCAL INVESTIGATION'):'VERTICAL PROFILING'):(d.exploration?.reason===1?'COMPLETE':d.exploration?.reason===6?'RECOVERY FAILED':'STOPPED / IDLE')):free?(swimRunning?(swimPaused?'PAUSED':autoPlanner?'AUTO SURVEY':'FREE SWIM'):'IDLE'):(states[r.state||0]||'Unknown').toUpperCase();$('depth').innerHTML=Number(r.depth_m||0).toFixed(2)+'<small> m</small>';$('target').textContent=activity==='explore'?`Target x ${Number(d.exploration?.target_x??0).toFixed(2)}, depth ${Number(d.exploration?.target_z??0).toFixed(2)} m`:free?'Manual depth control':'Target '+Number(r.target_depth_m||0).toFixed(2)+' m';$('velocity').innerHTML=(100*Number(r.vertical_mps||0)).toFixed(1)+'<small> cm/s</small>';$('limit').textContent=activity==='explore'?'Controller speed request '+(100*Number(r.speed_limit_mps||0)).toFixed(1)+' cm/s':free?'Toy drag + buoyancy':'Target rate '+(100*Number(r.speed_limit_mps||0)).toFixed(1)+' cm/s';const seconds=Math.floor((r.ms||0)/1000);$('clock-label').textContent=activity==='explore'?'SIMULATION CLOCK':offline?'RUN CLOCK':'BOARD CLOCK';$('clock').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');$('energy').textContent=activity!=='profile'?'Energy not modelled':Number(r.energy_j||0).toFixed(1)+' J · toy energy';$('temperature').innerHTML=Number(r.temperature_c??22).toFixed(2)+'<small> °C</small>';$('truth').innerHTML=(offline||activity==='explore'?Number(r.true_temperature_c??22).toFixed(2):'—')+'<small> °C</small>';$('cold').textContent=(22-water().drop).toFixed(0)+' °C';$('warm').textContent=['patch','combined'].includes(water().shape)?'24 °C':'22 °C';$('gradient').textContent=activity==='explore'?'Local fit shown in Thermal maps':'Gradient '+(r.gradient_valid?Number(r.gradient_cpm).toFixed(2):'—')+' °C/m';$('transition').textContent=activity==='explore'?(d.exploration?.mission_phase===8?'● Returning to saved descent checkpoint':d.exploration?.mission_phase===9?'● Ascending · local detours disabled':d.exploration?.mission_phase===7?'● Returning to descent':d.exploration?.mission_phase===6?'● Unvisited water · maximum 10 seconds':d.exploration?.mission_phase===5?'● Hold · next target within 8 seconds':d.exploration?.mission_phase===4?'● Experiment complete':d.exploration?.local?'● Local feature investigation':'● Vertical profiling / awaiting change'):r.transition?(active?(r.mode===0?'● Transition · slowing requested':'● Transition · fixed speed'):'● Transition detected during run'):'● No transition detected';$('transition').style.color=r.transition?'#eab878':'#8ce4c4';$('samples').textContent=(free?swimRows.length:rows.length)+' samples';
if(!offline&&!d.latest){$('temperature').textContent='— °C';$('depth').textContent='— m';$('velocity').textContent='— cm/s';$('state').textContent='AWAITING DATA';}
document.querySelector('.tank-note').textContent=activity==='explore'?`Memory: ${d.exploration?.known_cells||0} visited cells · local 8 s / unvisited water 10 s. Return to the saved x/depth checkpoint, resume descent, then surface.`:free?'True field shown in this tank. The estimator below receives only position and delayed probe readings.':offline?'The native controller receives the lagged probe measurement. Horizontal position is visual.':Object.keys(d.firmware_config||{}).length?'Water shading uses settings reported by the Nano. Depth and probe readings arrive over USB.':'Waiting for Nano settings. Water shading is a reference; no measurements have been assumed.';
document.querySelector('footer span:last-child').textContent=activity==='explore'?'Local 8 s · search 10 s · resume descent → surface':free?'Browser motion · 10 Hz sampling · user-defined survey budget':'20 Hz control · Nano firmware core · 180 s mission limit';const ex=d.exploration||{},reasons=['Running','Experiment complete','Reserved status','Invalid or unordered observation','Operator stop','Observation link timeout','Surface recovery timeout'];
document.querySelector('#thermal-mapping .eyebrow').textContent=activity==='explore'?'NANO / NATIVE ADAPTIVE EXPLORATION':free?'FREE SWIM / SPATIAL SAMPLING':'VERTICAL PROFILE / SPATIAL SAMPLING';$('explore-spot').disabled=active;$('explore-layers').disabled=active;
$('explore-link').textContent=offline?'Native C++ controller ready. Select Nano USB to run the same algorithm on the board.':d.identity?.startsWith('v0.14')?'Nano v0.14 verified. Probe observations → board; motion requests → lab.':'Connect Nano with firmware v0.14 for exploration.';
$('explore-report').textContent=`${ex.controller||'Controller'} · reply ${ex.sequence||0} · ${!ex.active&&ex.reason?'Stopped':ex.phase||'Broad survey'} · ${Number(ex.travel||0).toFixed(1)} m travelled · ${ex.visits||0} gradient regions · ${!d.running&&!ex.reason?'Ready':reasons[ex.reason||0]} · ${ex.local?'Local':'Last local'} 2D gradient ${ex.gradient_valid?`(${ex.gx.toFixed(2)}, ${ex.gz.toFixed(2)}) °C/m`:ex.visits?'incomplete for the most recent detour':'not yet sampled across both axes'}. Local status: ${['pending','predictable / weak / already sampled','8 s local limit','insufficient geometry / domain edge','temperature change: deliberate recheck','lag / detection margin exceeds the 8 s local allowance; boundary unresolved'][ex.local_exit||0]}. Memory: ${ex.known_cells||0} visited cells (0.125 m grid) · Local limit: 8 s · total unvisited-water phase: 10 s · return to checkpoint → descend → surface. Visited memory is retained until Reset / new run. Unsampled gaps remain unknown.`;
renderSettings();renderConsole();$('drive-stop').disabled=!free;$('keyboard-hint').classList.toggle('hidden',!free);document.querySelectorAll('[data-drive]').forEach(b=>{b.disabled=!free;b.classList.toggle('held',drive.has(b.dataset.drive));});
$('events').replaceChildren(...d.events.slice(0,4).map(e=>{const div=document.createElement('div');div.className='event';const time=document.createElement('time');time.textContent=e.time.toFixed(1)+'s';const span=document.createElement('span');span.textContent=e.text;div.append(time,span);return div;}));draw();}
function canvas(id){const c=$(id),box=c.getBoundingClientRect(),ratio=window.devicePixelRatio||1;if(c.width!==Math.round(box.width*ratio)||c.height!==Math.round(box.height*ratio)){c.width=Math.round(box.width*ratio);c.height=Math.round(box.height*ratio);}const ctx=c.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,box.width,box.height);return[ctx,box.width,box.height];}
function line(ctx,pts,color,dash=[]){ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=1.7;ctx.setLineDash(dash);pts.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));ctx.stroke();ctx.setLineDash([]);}
function drawSurveyRoute(c,X,Y){
 const report=autoPlanner?.report()||swim.survey;if(!report||!$('survey-route').checked)return;
 let previous=null;for(const p of report.route){if(previous)line(c,[[X(previous.x),Y(previous.z)],[X(p.x),Y(p.z)]],p.phase==='refinement'?'#ffc67a99':'#78baf5aa',[4,4]);previous=p;}
}
function drawTank(){
 const[c,w,h]=canvas('tank'),d=view()||{},r=d.latest||{},p=water(),free=activity==='swim',left=32,right=w-12,top=26,bottom=h-26,H=bottom-top,maxD=activity!=='profile'?3:1.5;
 const X=x=>left+x/8*(right-left),Y=z=>top+z/maxD*H;
 for(let ix=0;ix<48;ix++)for(let iz=0;iz<40;iz++){c.fillStyle=thermalColor(temperatureAt((ix+.5)/48*8,(iz+.5)/40*maxD,p),p);c.fillRect(left+ix/48*(right-left),top+iz/40*H,(right-left)/48+1,H/40+1);}
 c.strokeStyle='#54747c';c.strokeRect(left,top,right-left,H);c.font='10px system-ui';c.fillStyle='#91b7c2';c.fillText('8 m · VIRTUAL HORIZONTAL POSITION',left,top-11);
 for(let i=0;i<=6;i++){let z=maxD*i/6,y=Y(z);c.fillStyle='#9aadb9';c.fillText(z.toFixed(1),3,y+3);c.strokeStyle='#8aa5b32b';c.beginPath();c.moveTo(left,y);c.lineTo(right,y);c.stroke();}
 if(activity==='profile'){c.setLineDash([3,4]);c.strokeStyle='#ffffff66';c.beginPath();c.moveTo(X(profileX()),top);c.lineTo(X(profileX()),bottom);c.stroke();c.setLineDash([]);}
 if(free)drawSurveyRoute(c,X,Y);const path=free?swim.rows.map(r=>[r[1],r[2]]):activity==='explore'?rows.map(r=>[r.x_m,r.depth_m]):trail;line(c,path.map(([x,z])=>[X(x),Y(z)]),'#8ce4c455');
 if(activity==='explore'&&snapshot?.exploration?.active){const ex=snapshot.exploration;c.strokeStyle=ex.local?'#ffc67a':'#78baf5';c.lineWidth=2;c.beginPath();c.arc(X(ex.target_x),Y(ex.target_z),6,0,Math.PI*2);c.stroke();}
 const x=X(free?swim.x:activity==='explore'?profileX():visualX),y=Y(Number(r.depth_m||0));
 c.fillStyle='#142b36';c.strokeStyle='#b2d0d8';c.lineWidth=2;c.beginPath();c.roundRect(x-24,y-10,48,20,8);c.fill();c.stroke();c.fillStyle='#e9ba7a';c.fillRect(x-8,y-5,18,10);
 c.fillStyle='#11212c';for(const dx of[-25,25]){c.beginPath();c.ellipse(x+dx,y,4,9,0,0,Math.PI*2);c.fill();c.stroke();}c.strokeStyle='#8ce4c4';c.beginPath();c.moveTo(x+6,y+10);c.lineTo(x+6,y+19);c.lineTo(x+17,y+19);c.stroke();c.fillStyle='#8ce4c4';c.beginPath();c.arc(x+18,y+19,3,0,Math.PI*2);c.fill();
 $('position-note').textContent=`x ${(free?swim.x:activity==='explore'?profileX():visualX).toFixed(2)} m (simulated) · depth ${Number(r.depth_m||0).toFixed(2)} m (${free?'browser':activity==='explore'?(snapshot?.source==='nano'?'lab plant · Nano control':'lab plant · native control'):snapshot?.source==='nano'?(snapshot?.verified?'Nano telemetry':'awaiting Nano'):'native controller'})`;
}

function chart(id,isProfile){const d=view()||{},data=activity==='swim'?swimRows:rows;const[c,w,h]=canvas(id),pad={l:39,r:14,t:10,b:27},W=w-pad.l-pad.r,H=h-pad.t-pad.b;const p=water(),maxD=activity!=='profile'?3:1.5;const minimum=Math.min(18,22-p.drop-.3),maxTemp=['patch','combined'].includes(p.shape)?24.5:22.5;const maxTime=Math.max(30,(d.latest?.ms||0)/1000);const X=v=>pad.l+(isProfile?(v-minimum)/(maxTemp-minimum):v/maxTime)*W,Y=v=>pad.t+v/maxD*H;c.font='9px system-ui';for(let i=0;i<=4;i++){const depth=i*maxD/4,y=Y(depth);c.strokeStyle='#263a46';c.beginPath();c.moveTo(pad.l,y);c.lineTo(w-pad.r,y);c.stroke();c.fillStyle='#8199a8';c.fillText(depth.toFixed(1),7,y+3);}for(let i=0;i<=4;i++){const value=isProfile?minimum+(maxTemp-minimum)*i/4:maxTime*i/4,x=X(value);c.fillStyle='#8199a8';c.fillText(value.toFixed(isProfile?1:0),x-9,h-10);}c.fillStyle='#657f8d';c.fillText(isProfile?'°C':'s',w-10,h-10);c.fillText('m',7,8);
const sampled=data.filter((_,i)=>i%Math.max(1,Math.floor(data.length/1600))===0);if(isProfile&&activity==='profile'&&snapshot?.source!=='nano'){const curve=[];for(let d=0;d<=maxD;d+=.01){const t=temperatureAt(profileX(),d,p);curve.push([X(t),Y(d)]);}line(c,curve,'#eab878',[4,4]);}
c.save();c.beginPath();c.rect(pad.l,pad.t,W,H);c.clip();if(isProfile){if(activity!=='profile')line(c,sampled.map(r=>[X(r.true_temperature_c),Y(r.depth_m)]),'#eab878',[4,4]);line(c,sampled.map(r=>[X(r.temperature_c),Y(r.depth_m)]),'#8ce4c4');}else{for(let i=1;i<sampled.length;i++)if(sampled[i].transition){c.fillStyle='#eab87812';c.fillRect(X(sampled[i-1].ms/1000),pad.t,X(sampled[i].ms/1000)-X(sampled[i-1].ms/1000),H);}line(c,sampled.map(r=>[X(r.ms/1000),Y(r.depth_m)]),'#74b9e1');line(c,sampled.map(r=>[X(r.ms/1000),Y(r.target_depth_m)]),'#8ce4c4',[4,4]);}c.restore();}
function thermalColor(value,p){
 const low=22-p.drop,high=['patch','combined'].includes(p.shape)?24:22;
 const f=Math.max(0,Math.min(1,(value-low)/Math.max(.1,high-low)));
 return `rgb(${Math.round(25+173*f)},${Math.round(67+82*f)},${Math.round(116-33*f)})`;
}
function arrow(c,x,y,g,W,H){
 if(!g||Math.hypot(g.gx,g.gz)<.03)return;
 let dx=g.gx*W/8,dy=g.gz*H/3,n=Math.hypot(dx,dy);dx=dx/n*12;dy=dy/n*12;
 c.strokeStyle='#e5f5e8';c.lineWidth=1.2;c.beginPath();c.moveTo(x-dx/2,y-dy/2);c.lineTo(x+dx/2,y+dy/2);c.lineTo(x+dx/2-dx*.35-dy*.25,y+dy/2-dy*.35+dx*.25);c.moveTo(x+dx/2,y+dy/2);c.lineTo(x+dx/2-dx*.35+dy*.25,y+dy/2-dy*.35-dx*.25);c.stroke();
}
function drawMaps(){
 if(document.body.dataset.view!=='maps')return;const p=water(),key=JSON.stringify(p),now=performance.now(),NX=32,NZ=20;
 if(!mapCache||mapCache.key!==key||(mapCache.version!==thermalMap.version&&now-mapUpdated>1000)){
  const nodes=[];let sum=0,count=0;
  for(let iz=0;iz<=NZ;iz++)for(let ix=0;ix<=NX;ix++){
   const x=ix/NX*8,z=iz/NZ*3,truth=temperatureAt(x,z,p),estimate=thermalMap.estimate(x,z);nodes.push({x,z,truth,estimate});
   if(estimate?.gradient&&estimate.coverage>.15){sum+=(estimate.temperature-truth)**2;count++;}
  }
  mapCache={key,version:thermalMap.version,nodes,rmse:count?Math.sqrt(sum/count):null,count};mapUpdated=now;
 }
 $('map-export').disabled=!thermalMap.samples;const {nodes}=mapCache,at=(ix,iz)=>nodes[iz*(NX+1)+ix],coverage=$('map-display').value==='coverage';
 for(const [id,isTruth]of [['map-truth',true],['map-estimate',false]]){
  const[c,w,h]=canvas(id),left=32,top=15,W=w-left-12,H=h-top-29,X=x=>left+x/8*W,Y=z=>top+z/3*H;
  c.fillStyle='#17212c';c.fillRect(left,top,W,H);
  for(let iz=0;iz<NZ;iz++)for(let ix=0;ix<NX;ix++){
   const node=at(ix,iz),e=node.estimate;if(!isTruth&&!e)continue;
   c.globalAlpha=isTruth||coverage?1:.2+.8*e.coverage;
   c.fillStyle=isTruth?thermalColor(node.truth,p):coverage?`rgb(${Math.round(35+70*e.coverage)},${Math.round(45+155*e.coverage)},${Math.round(60+100*e.coverage)})`:thermalColor(e.temperature,p);
   c.fillRect(X(node.x),Y(node.z),W/NX+1,H/NZ+1);
  }c.globalAlpha=1;
  if($('map-boundary').checked&&(!coverage||isTruth)&&(p.drop>.001||['patch','combined'].includes(p.shape))){
   const mid=p.drop===0&&['patch','combined'].includes(p.shape)?23:22-p.drop/2;c.strokeStyle='#fff1b6';c.lineWidth=1.2;c.setLineDash([3,3]);
   for(let iz=0;iz<NZ;iz++)for(let ix=0;ix<NX;ix++){
    const corners=[at(ix,iz),at(ix+1,iz),at(ix+1,iz+1),at(ix,iz+1)],crossings=[];
    if(!isTruth&&corners.some(n=>!n.estimate))continue;
    const value=n=>isTruth?n.truth:n.estimate.temperature;
    for(let edge=0;edge<4;edge++){const a=corners[edge],b=corners[(edge+1)%4],va=value(a),vb=value(b);if(Math.abs(va-mid)<1e-6&&Math.abs(vb-mid)<1e-6)continue;if((va<mid)===(vb<mid))continue;const t=(mid-va)/(vb-va);crossings.push([X(a.x+t*(b.x-a.x)),Y(a.z+t*(b.z-a.z))]);}
    for(let i=0;i+1<crossings.length;i+=2){c.beginPath();c.moveTo(...crossings[i]);c.lineTo(...crossings[i+1]);c.stroke();}
   }c.setLineDash([]);
  }
  if($('map-arrows').checked)for(let iz=2;iz<NZ;iz+=4)for(let ix=2;ix<NX;ix+=4){const node=at(ix,iz),e=node.estimate;arrow(c,X(node.x),Y(node.z),isTruth?trueGradient(node.x,node.z,p):e?.coverage>.15?e.gradient:null,W,H);}
  c.save();c.beginPath();c.rect(left,top,W,H);c.clip();
  if(activity==='swim')drawSurveyRoute(c,X,Y);
  line(c,(activity==='swim'?swim.rows.map(r=>[r[1],r[2]]):rows.map(r=>[r.profile_x_m??profileX(),r.depth_m])).map(([x,z])=>[X(x),Y(z)]),'#eef7ee66');
  if(!isTruth)for(const cell of thermalMap.cells.values()){c.fillStyle=thermalColor(cell.t,p);c.beginPath();c.arc(X(cell.x),Y(cell.z),1.5,0,Math.PI*2);c.fill();}
  c.restore();c.fillStyle='#ffffff';c.beginPath();c.arc(X(activity==='swim'?swim.x:profileX()),Y(activity==='swim'?swim.z:(snapshot?.latest?.depth_m||0)),3,0,Math.PI*2);c.fill();
  c.strokeStyle='#536b79';c.strokeRect(left,top,W,H);c.font='10px system-ui';c.fillStyle='#9ab0ba';
  for(let z=0;z<=3;z++){c.fillText(z+' m',1,Y(z)+3);}for(let x=0;x<=8;x+=2)c.fillText(x+' m',X(x)-6,h-8);
 }
 const local=thermalMap.estimate(activity==='swim'?swim.x:profileX(),activity==='swim'?swim.z:(snapshot?.latest?.depth_m||0)),g=local?.gradient;
 $('map-count').textContent=`${thermalMap.cells.size} measured cells · ${thermalMap.samples} readings`;
 $('map-gradient').textContent=g?`Estimated gradient: (${g.gx.toFixed(2)}, ${g.gz.toFixed(2)}) °C/m · strength ${Math.hypot(g.gx,g.gz).toFixed(2)} °C/m`:`At vehicle: gradient unavailable (${local?.reason||'collect samples across x and depth'})`;
 $('map-error').textContent=mapCache.rmse===null?'Supported-grid RMSE: —':`Supported-grid RMSE: ${mapCache.rmse.toFixed(2)} °C (${mapCache.count} grid points)`;
 $('map-scale').textContent=p.drop<=.001&&!['patch','combined'].includes(p.shape)?'Uniform 22 °C reference · no distinct isotherm':`Colours: ${(22-p.drop).toFixed(1)}–${['patch','combined'].includes(p.shape)?24:22} °C · contour ${(p.drop===0&&['patch','combined'].includes(p.shape)?23:22-p.drop/2).toFixed(1)} °C`;
 $('map-explanation').textContent=`At vehicle: ${local?.reason||'No nearby observations'}. Arrows show direction toward warmer water; arrow lengths are normalized. Map error uses simulator truth for evaluation only. Probe lag can bias the map even with good spatial support.`;
}

function draw(){drawTank();chart('profile',true);chart('timeline',false);drawMaps();}window.addEventListener('resize',draw);labels();poll();setInterval(poll,250);requestAnimationFrame(frame);

let researchResult=null,researchBusy=false;
function renderResearch(result){
 researchResult=result;const body=$('research-results');body.replaceChildren();
 const mean=(values)=>values.length?values.reduce((a,b)=>a+b,0)/values.length:null;
 const display=(value,scale=1)=>value===null?'—':(value*scale).toFixed(2);
 for(const mode of ['adaptive','fast','slow'])for(const leg of ['descent','ascent']){
  const metrics=result.metrics.filter(r=>r.mode===mode&&r.direction===leg),trials=result.trials.filter(r=>r.mode===mode);
  const average=key=>mean(metrics.map(r=>r[key]).filter(v=>v!==null));
  const values=[mode+' / '+leg,display(average('common_depth_rmse_c')),display(average('transition_rmse_c')),display(average('boundary_depth_error_m'),100),display(average('occupied_bins'),100/36),display(mean(trials.map(r=>r.elapsed_s)))];
  const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);
 }
 const complete=result.trials.filter(r=>r.complete).length,censored=result.trials.filter(r=>r.censored).length,faults=result.trials.filter(r=>r.faults).length;
 const common=Math.min(...result.metrics.map(r=>r.common_bins)),missing=result.metrics.filter(r=>r.boundary_depth_error_m===null).length;
 $('research-status').textContent=`${complete}/${result.trials.length} profiles complete · ${censored} allowance-censored · ${faults} faults · minimum shared bins ${common}/36 · ${missing} undefined / uncrossed boundary estimates. Reference boundary: ${result.reference_boundary_m===null?'undefined in this column':result.reference_boundary_m.toFixed(3)+' m'}. Actual τ ${result.params.tau} s; assumed τ ${result.controller_config.probe_tau_s} s. Files saved under output/experiments/profile_comparison. No physical validation is implied.`;
 $('research-export').disabled=false;
}
$('research-run').onclick=async()=>{
 if(researchBusy)return;researchBusy=true;$('research-run').disabled=true;$('research-status').textContent='Comparing the native controller with the same allowance and paired noise…';
 try{await request('/api/action',{action:'research',...config(),shape:$('thermal-shape').value});renderResearch(await(await request('/api/research')).json());}
 catch(e){$('research-status').textContent=e.message;}
 finally{researchBusy=false;$('research-run').disabled=false;}
};
$('research-export').onclick=async()=>{try{download(await(await request('/api/research.csv')).blob(),'pelagic-profile-trials.csv');}catch(e){$('research-status').textContent=e.message;}};
