// Coverage before exploitation. Receives position/time/probe temperature only.
// No simulator temperature function or hidden patch coordinates are available here.
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
export class SurveyPlanner {
  constructor({policy='adaptive',spacing=.5,targetCoverage=.9,threshold=.15,budget=240,maxRefinements=4}={}){
    if(!['diagonal','sweep','adaptive'].includes(policy))throw Error('Unknown survey policy');
    if(![spacing,targetCoverage,threshold,budget,maxRefinements].every(Number.isFinite))throw Error('Invalid planner settings');
    this.policy=policy;this.spacing=clamp(spacing,.25,1);this.targetCoverage=clamp(targetCoverage,.7,1);this.threshold=clamp(threshold,.05,2);this.budget=clamp(budget,30,360);this.maxRefinements=clamp(Math.floor(maxRefinements),0,6);
    this.index=0;this.phase='coverage';this.done=false;this.reason='';this.refinements=[];this.observations=new Map();this.distance=0;this.elapsed=0;this.previous=null;this.events=[];
    const left=.4,right=7.6,top=.2,bottom=2.7;
    this.route=[];const add=(x,z)=>this.route.push({x,z,phase:'coverage'});
    if(policy==='diagonal'){add(left,top);add(right,bottom);add(right,top);add(left,bottom);}
    else{const rows=Math.ceil((bottom-top)/this.spacing);for(let row=0;row<=rows;row++){const z=top+row/rows*(bottom-top);add(row%2?right:left,z);add(row%2?left:right,z);}}
    this.grid=[];for(let iz=0;iz<18;iz++)for(let ix=0;ix<48;ix++)this.grid.push({x:left+(ix+.5)/48*(right-left),z:top+(iz+.5)/18*(bottom-top),seen:false});
  }
  coverage(){return this.grid.filter(p=>p.seen).length/this.grid.length;}
  observe({x,z,temperature,t}){
    if(![x,z,temperature,t].every(Number.isFinite))return;
    if(this.previous)this.distance+=Math.hypot(x-this.previous.x,z-this.previous.z);
    this.previous={x,z};this.elapsed=t;
    const key=`${Math.floor(x/.2)}:${Math.floor(z/.1)}`,cell=this.observations.get(key)||{x:0,z:0,temperature:0,n:0};cell.n++;
    for(const [k,v]of Object.entries({x,z,temperature}))cell[k]+=(v-cell[k])/cell.n;
    this.observations.set(key,cell);
    for(const p of this.grid)if(!p.seen&&Math.hypot(p.x-x,p.z-z)<=this.spacing/2)p.seen=true;
  }
  chooseRefinement(){
    // Finish the broad survey before considering local detours.
    const cells=[...this.observations.values()];let best=null;
    for(const a of cells){
      if(this.refinements.some(p=>Math.hypot(p.x-a.x,p.z-a.z)<.8))continue;
      let score=0;
      for(const b of cells){const distance=Math.hypot(a.x-b.x,a.z-b.z),change=Math.abs(a.temperature-b.temperature);if(distance>.15&&distance<.8&&change>=this.threshold)score=Math.max(score,change/distance);}
      if(score>0&&(!best||score>best.score))best={x:a.x,z:a.z,score,kind:'temperature change'};
    }
    let gap=null;
    if(this.coverage()<this.targetCoverage){
      // A quiet region can still deserve a visit: pick its most distant unsampled cell.
      for(const p of this.grid.filter(p=>!p.seen)){
        if(this.refinements.some(a=>Math.hypot(a.x-p.x,a.z-p.z)<.8))continue;
        let nearest=Infinity;for(const a of cells)nearest=Math.min(nearest,Math.hypot(a.x-p.x,a.z-p.z));
        if(!gap||nearest>gap.score)gap={x:p.x,z:p.z,score:nearest,kind:'coverage gap'};
      }
    }
    return gap||best;
  }
  appendRefinement(p){
    this.refinements.push(p);this.phase='refinement';this.events.push({time:this.elapsed,text:`Refine ${p.kind} near (${p.x.toFixed(2)}, ${p.z.toFixed(2)}) m`});
    // Cross from two directions, then encircle the candidate; no truth-gradient following.
    for(const [dx,dz]of [[-.45,0],[.45,0],[0,0],[0,-.28],[0,.28],[-.45,-.28],[.45,-.28],[.45,.28],[-.45,.28],[0,0]])this.route.push({x:clamp(p.x+dx,.4,7.6),z:clamp(p.z+dz,.2,2.7),phase:'refinement'});
  }
  update(position){
    if(this.done)return null;
    this.elapsed=position.t;
    if(position.t>=this.budget){this.finish('Time budget reached');return null;}
    while(this.index<this.route.length){const p=this.route[this.index];if(Math.abs(p.x-position.x)<.12&&Math.abs(p.z-position.z)<.08)this.index++;else{this.phase=p.phase;return p;}}
    if(this.policy!=='adaptive'){this.finish(this.coverage()>=this.targetCoverage?'Planned coverage route completed':'Route completed below coverage goal');return null;}
    const next=this.chooseRefinement();
    if(next&&this.refinements.length<this.maxRefinements){this.appendRefinement(next);return this.route[this.index];}
    this.finish(next?'Local refinement limit reached':this.coverage()>=this.targetCoverage?'Coverage target met; no remaining qualifying change':'Coverage route ended below target');return null;
  }
  finish(reason){this.done=true;this.reason=reason;this.phase='complete';this.events.push({time:this.elapsed,text:reason});}
  report(){return {policy:this.policy,spacing:this.spacing,radius:this.spacing/2,targetCoverage:this.targetCoverage,threshold:this.threshold,budget:this.budget,coverage:this.coverage(),reached:this.index,total:this.route.length,refinements:this.refinements.length,phase:this.phase,reason:this.reason,distance:this.distance,seconds:this.elapsed,coverageMet:this.coverage()>=this.targetCoverage,events:this.events,route:this.route,targets:this.refinements};}
}

export function surveyControls(position,target){
  const slow=target.phase==='refinement',surgeLimit=slow?.35:1,heaveLimit=slow?.45:1;
  return {surge:clamp(2.5*(target.x-position.x)-2*position.vx,-surgeLimit,surgeLimit),heave:clamp(4*(target.z-position.z)-2*position.vz+.03,-heaveLimit,heaveLimit)};
}
