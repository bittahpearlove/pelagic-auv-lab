import assert from 'node:assert/strict';
import {SurveyPlanner,surveyControls} from '../lab/static/survey-planner.mjs';
import {generateSurvey} from '../lab/static/demo-model.mjs';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../lab/static/survey-planner.mjs',import.meta.url),'utf8');
assert(!source.includes('temperatureAt(')&&!source.includes('trueGradient('),'Planner cannot access the simulator field');
assert.throws(()=>new SurveyPlanner({budget:NaN}));assert.throws(()=>new SurveyPlanner({policy:'magic'}));
const quiet=new SurveyPlanner();for(let i=0;i<10;i++)quiet.observe({x:1+i*.1,z:1,temperature:22,t:i});
// Disable gap priority to isolate the temperature trigger.
quiet.targetCoverage=0;assert.equal(quiet.chooseRefinement(),null,'Uniform measurements must not trigger thermal refinement');
quiet.observe({x:1.5,z:1.2,temperature:23,t:10});const candidate=quiet.chooseRefinement();assert.equal(candidate.kind,'temperature change');
quiet.appendRefinement(candidate);assert(quiet.route.every(p=>p.x>=.4&&p.x<=7.6&&p.z>=.2&&p.z<=2.7));
const gap=new SurveyPlanner();gap.observe({x:1,z:1,temperature:22,t:0});assert.equal(gap.chooseRefinement().kind,'coverage gap','Quiet but unvisited water still needs exploration');
const sampleCount=gap.observations.size;gap.observe({x:NaN,z:1,temperature:22,t:1});assert.equal(gap.observations.size,sampleCount);
const timed=new SurveyPlanner({budget:30});assert.equal(timed.update({x:2,z:1,t:30}),null);assert.equal(timed.reason,'Time budget reached');
const slow=surveyControls({x:1,z:1,vx:0,vz:0},{x:6,z:2,phase:'refinement'});assert.equal(slow.surge,.35);assert.equal(slow.heave,.45);
const flat={shape:'layer',center:1.3,width:.07,drop:0,tau:2};
const noFeature=generateSurvey(flat,{policy:'adaptive',spacing:.5,budget:240});assert.equal(noFeature.report.refinements,0);assert(noFeature.report.coverageMet);
const patch={...flat,shape:'patch'};
const reports={};for(const policy of ['diagonal','sweep','adaptive']){
 const result=generateSurvey(patch,{policy,spacing:.5,targetCoverage:.9,threshold:.15,budget:240});reports[policy]=result.report;
 assert(result.report.seconds<=240.051,'Budget must bound a run');assert(result.demo.rows.every(r=>r[1]>=.2&&r[1]<=7.8&&r[2]>=.08&&r[2]<=2.85));
}
assert(reports.diagonal.coverage<.5,'Crossed diagonals should expose their coverage gaps');assert(reports.sweep.coverage>.95);assert(reports.sweep.coverage>reports.diagonal.coverage);
assert.equal(reports.sweep.refinements,0);assert(reports.adaptive.refinements>0,'Measured patch signal triggers local investigation');
assert(reports.adaptive.events.some(e=>e.text.includes('temperature change')));assert.equal(reports.adaptive.reason,'Time budget reached','Coverage goal alone must not conceal unfinished local work');
console.log('PASS: measured-only planning, quiet-region exploration, thermal trigger, bounds, slow refinement, budget and coverage comparison');
console.log(JSON.stringify(Object.fromEntries(Object.entries(reports).map(([p,r])=>[p,{coverage:r.coverage,seconds:r.seconds,distance:r.distance,refinementsStarted:r.refinements,reason:r.reason}]))));
