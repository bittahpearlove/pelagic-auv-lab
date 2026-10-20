import assert from 'node:assert/strict';
import {selectedReconstruction,summarize,depthStatuses,flatMissionCounts} from '../lab/static/research-summary.mjs';
assert.equal(selectedReconstruction('response','primary'),'forward');
assert.equal(selectedReconstruction('medium','primary'),'raw');
const rows=[{boundary_expected:true,boundary_depth_error_m:.01,boundary_loss_m:.01,full_profile_rmse_c:.02},{boundary_expected:true,boundary_depth_error_m:null,boundary_loss_m:.3,full_profile_rmse_c:null}];
const s=summarize(rows);assert.equal(s.detected,1);assert.equal(s.missed,1);assert.equal(s.fullAvailable,1);assert.equal(s.avg('boundary_loss_m'),.155);
assert.deepEqual(depthStatuses([{status_by_depth:[{depth_m:.2,samples:2,counts:{good:2}}]},{status_by_depth:[{depth_m:.2,samples:1,counts:{geometry:1}}]}]),[{depth_m:.2,samples:3,counts:{good:2,geometry:1}}]);
console.log('Research display aggregation passed');

assert.deepEqual(flatMissionCounts([{scenario_id:'s1',mode:'response',boundary_expected:false,false_boundary_peaks:0},{scenario_id:'s1',mode:'response',boundary_expected:false,false_boundary_peaks:2},{scenario_id:'s2',mode:'response',boundary_expected:false,false_boundary_peaks:0},{scenario_id:'s3',mode:'response',boundary_expected:true,false_boundary_peaks:0}]),{missions:2,falsePositiveMissions:1});
