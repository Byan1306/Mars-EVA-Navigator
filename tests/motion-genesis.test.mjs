import test from 'node:test';
import assert from 'node:assert/strict';
import {solveLegIK,groundNormal,raisedFoot,advancePhase} from '../astronaut_motion/math.mjs';
import {motionQuality} from '../astronaut_motion/quality.mjs';
import {createTerrainSampler} from '../astronaut_motion/terrain_adapter.mjs';
import {createMotionMetrics} from '../astronaut_motion/metrics.mjs';
function footFromIK(s,L1=.41,L2=.36){
 const a=s.hip,b=s.shin;
 return [-L1*Math.cos(a)-L2*Math.cos(a+b),-L1*Math.sin(a)-L2*Math.sin(a+b)];
}
test('forward-bending femur and tibia IK matches real world foot target',()=>{
 for(const [y,z] of [[-.68,0],[-.64,-.18],[-.58,.22]]){
  const result=solveLegIK(y,z);
  assert.ok(result);const [actualY,actualZ]=footFromIK(result);
  assert.ok(Math.abs(y-actualY)<1e-6);
  assert.ok(Math.abs(z-actualZ)<1e-6);
  assert.ok(result.flexion>0);
 }
});
test('impossible IK reach is safely clamped',()=>{
 for(const [y,z] of [[-10,12],[0,0]]){
  const q=solveLegIK(y,z);assert.ok(q.unreachable);
  assert.ok(Number.isFinite(q.hip)&&Number.isFinite(q.shin));
 }
});
test('DEM slope normal derives from measured heights without modifying them',()=>{
 const src=(x,z)=>-2600+.12*x-.08*z;
 const n=groundNormal(src,3,4);
 assert.ok(n);
 assert.ok(Math.abs(n[0]+.12*n[1])<1e-6);
 assert.ok(Math.abs(n[2]-.08*n[1])<1e-6);
 const adapter=createTerrainSampler(src);
 assert.ok(Math.abs(adapter.height(10,10)+2599.6)<1e-8);
});
test('NoData is not converted to artificial geometry',()=>{
 const s=createTerrainSampler((x,z)=>x>0?null:-2600);
 assert.equal(s.height(2,0),null);assert.equal(s.normal(0,0),null);
});
test('swing arc is above terrain and planted at endpoints',()=>{
 assert.equal(raisedFoot(0,.2),0);
 assert.ok(raisedFoot(.5,.2)>.19);
 assert.ok(raisedFoot(1,.2)<1e-15);
});
test('distance driven gait is invariant to frame rate',()=>{
 let a=0,b=0;
 for(let i=0;i<30;i++)a=advancePhase(a,1.45/30);
 for(let i=0;i<60;i++)b=advancePhase(b,1.45/60);
 assert.ok(Math.abs(a-b)<1e-8);
});
test('quality budgets throttle IK rather than costly full skeleton simulation',()=>{
 assert.equal(motionQuality('low').ikHz,20);
 assert.equal(motionQuality('balanced').ikHz,30);
 assert.equal(motionQuality('high').ikHz,60);
});
test('measurement counters report observed, not guessed hardware FPS',()=>{
 const m=createMotionMetrics();for(let i=0;i<120;i++)m.tick(1/60,2);
 assert.equal(m.read().fps,60);
 assert.equal(m.read().ikSolvesPerSecond,120);
});
