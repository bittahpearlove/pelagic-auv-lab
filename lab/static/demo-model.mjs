import {temperatureAt} from './thermal-map.mjs';
import {SurveyPlanner,surveyControls} from './survey-planner.mjs';
// Browser-only plant: deliberately separate from Nano control/serial commands.
export class MovementDemo {
  constructor(){this.reset();}
  reset(){this.x=2;this.z=.35;this.vx=0;this.vz=0;this.t=0;this.measured=22;this.truth=22;this.rows=[];this.path=[];this.surge=0;this.heave=0;this.sampleClock=0;}
  step(dt,surge,heave,tau=2,water={center:1.3,width:.12,drop:3}){
    if(!Number.isFinite(dt)||dt<=0)return;
    dt=Math.min(dt,.05);tau=Math.max(.1,Math.min(8,tau));
    this.surge=Math.max(-1,Math.min(1,surge));this.heave=Math.max(-1,Math.min(1,heave));
    this.vx+=(.8*this.surge-1.4*this.vx)*dt;
    this.vz+=(.6*this.heave-1.8*this.vz-.018)*dt;
    this.x+=this.vx*dt;this.z+=this.vz*dt;
    if(this.x<.2){this.x=.2;this.vx=0;}if(this.x>7.8){this.x=7.8;this.vx=0;}
    if(this.z<.08){this.z=.08;this.vz=0;}if(this.z>2.85){this.z=2.85;this.vz=0;}
    this.t+=dt;this.truth=temperatureAt(this.x,this.z,water);
    this.measured+=(this.truth-this.measured)*(1-Math.exp(-dt/tau));
    this.sampleClock+=dt;
    if(this.sampleClock>=.1){this.sampleClock-=.1;this.path.push([this.x,this.z]);this.rows.push([this.t,this.x,this.z,this.vx,this.vz,this.truth,this.measured,this.surge,this.heave]);if(this.rows.length>6000)this.rows.shift();if(this.path.length>2000)this.path.shift();}
  }
}

export function generateSurvey(water,options={policy:'sweep',spacing:.4}){
  const demo=new MovementDemo(),planner=new SurveyPlanner(options);
  // A stationary initial reading; the planner receives it as an observation.
  demo.truth=demo.measured=temperatureAt(demo.x,demo.z,water);
  planner.observe({x:demo.x,z:demo.z,temperature:demo.measured,t:0});
  while(!planner.done){
    const target=planner.update(demo);if(!target)break;
    const before=demo.rows.at(-1),controls=surveyControls(demo,target);
    demo.step(.05,controls.surge,controls.heave,water.tau,water);
    if(demo.rows.at(-1)!==before)planner.observe({x:demo.x,z:demo.z,temperature:demo.measured,t:demo.t});
  }
  const report=planner.report();demo.survey=report;
  return {demo,reached:report.reached,total:report.total,report};
}
