/* NASA Z-2 outer suit, educational 206-bone rig. Grounded gait V5.
 * Height and normals originate from measured CTX DEM; no synthetic geology.
 */
import {advancePhase,clamp,lerp,raisedFoot,smoothstep,solveLegIK} from './math.mjs';
import {motionQuality} from './quality.mjs';
import {createTerrainSampler} from './terrain_adapter.mjs';
import {createMotionMetrics} from './metrics.mjs';
export function createAstronautMotion({THREE,root,gltf,sampleGround,quality='balanced',mocap=null}){
 const skins=[];root.traverse(n=>{if(n.isSkinnedMesh)skins.push(n)});
 if(!skins.length)throw Error('NASA Z2 must be a SkinnedMesh');
 const bones=skins[0].skeleton.bones;
 if(bones.length!==206)throw Error('206 anatomical joints required, received '+bones.length);
 const byName=Object.fromEntries(bones.map(b=>[b.name,b]));
 for(const n of ['L_Femur','R_Femur','L_Tibia','R_Tibia','L_Tarsal_Talus',
  'R_Tarsal_Talus','L_Humerus','R_Humerus','Sacrum','Lumbar_L3','Thoracic_T7'])
  if(!byName[n])throw Error('Required anatomical joint absent: '+n);
 const mixer=new THREE.AnimationMixer(root),actions={};
 for(const clip of gltf.animations||[]){
  if(['idle','walk','fast_walk'].includes(clip.name)){
   actions[clip.name]=mixer.clipAction(clip).setLoop(THREE.LoopRepeat).play();
   actions[clip.name].setEffectiveWeight(clip.name==='idle'?1:0);
  }
 }
 if(!actions.idle||!actions.walk||!actions.fast_walk)throw Error('Missing educational gait clips');

 function loadRecordedHumanMotion(data){
   if(!data || data.format!=='MarsEVA-CMU-HumanWalk-v1' ||
      !Array.isArray(data.tracks) || data.tracks.length<18 ||
      !Array.isArray(data.times) || data.times.length<40)return null;
   const times=Float32Array.from(data.times),tracks=[];
   if(Math.abs(times[times.length-1]-data.duration_seconds)>.0001)return null;
   for(const t of data.tracks){
     if(!byName[t.bone]||t.quats?.length!==times.length*4)return null;
     tracks.push(new THREE.QuaternionKeyframeTrack(t.bone+'.quaternion',times,Float32Array.from(t.quats)));
   }
   if(data.root_sway_xy?.length!==times.length*2)return null;
   const clip=new THREE.AnimationClip('CMU_human_walk',data.duration_seconds,tracks);
   return {action:mixer.clipAction(clip).play(),data,times};
 }
 const recorded=loadRecordedHumanMotion(mocap);
 if(recorded)recorded.action.setEffectiveWeight(0);
 const torso=byName.Sacrum,torsoRest=torso.position.clone();
 const terrain=createTerrainSampler(sampleGround),metrics=createMotionMetrics();
 const feet=[{side:-1,upper:byName.L_Femur,lower:byName.L_Tibia,foot:byName.L_Tarsal_Talus},
  {side:1,upper:byName.R_Femur,lower:byName.R_Tibia,foot:byName.R_Tarsal_Talus}]
  .map(f=>({...f,lock:new THREE.Vector3(),begin:new THREE.Vector3(),
   end:new THREE.Vector3(),target:new THREE.Vector3(),neutral:new THREE.Vector3(),
   hasLock:false,swing:false,planted:true,
   priorHip:new THREE.Quaternion(),priorKnee:new THREE.Quaternion(),
   priorFoot:new THREE.Quaternion(),sole:new THREE.Vector3()}));
 const v=new THREE.Vector3(),temp=new THREE.Vector3(),scale=new THREE.Vector3();
 const inverse=new THREE.Matrix4();
 let phase=0,speed=0,lastX=NaN,lastZ=NaN,ikAccum=0,updates=0;
 let mode='idle',lastFacing=null,turnRate=0,slipCorrections=0,qualityName=quality,source='procedural';
 function neutral(leg,out=leg.neutral){
  v.set(leg.side*.212,.10,-.07);
  out.copy(root.localToWorld(v));return out;
 }
 function pinToMeasuredSurface(target,clearance){
  const h=terrain.height(target.x,target.z);
  if(h===null)return false;
  target.y=h+clearance;return true;
 }
 function solveFoot(leg,world,normal){
  temp.copy(world);leg.upper.parent.worldToLocal(temp);
  const solution=solveLegIK(temp.y-leg.upper.position.y,temp.z-leg.upper.position.z,.41,.36);
  if(!solution)return false;
  leg.upper.rotation.x=clamp(solution.hip,-1.16,1.16);
  leg.lower.rotation.x=clamp(solution.shin,-1.58,0);
  let pitch=0,roll=0;
  if(normal){
   v.set(normal[0],normal[1],normal[2]).transformDirection(inverse);
   pitch=clamp(-Math.atan2(-v.z,Math.max(.6,v.y)),-.26,.26);
   roll=clamp(Math.atan2(v.x,Math.max(.6,v.y)),-.22,.22);
  }
  leg.foot.rotation.x=clamp(-leg.upper.rotation.x-leg.lower.rotation.x+pitch,-.72,.72);
  leg.foot.rotation.z=roll;
  return true;
 }
 function reset(){
  phase=0;speed=0;lastX=NaN;lastZ=NaN;ikAccum=0;
  lastFacing=null;turnRate=0;
  feet.forEach(f=>{f.hasLock=false;f.swing=false;f.planted=true});
  metrics.reset();
 }
 function update({dt,player,active=true,fly=false,quality:nextQuality=qualityName}){
  if(!Number.isFinite(dt)||dt<=0)return getState();
  dt=Math.min(dt,.08);qualityName=nextQuality;
  const cfg=motionQuality(qualityName);
  let dx=0,dz=0,distance=0;
  if(Number.isFinite(lastX)&&Number.isFinite(lastZ)){
   dx=player.x-lastX;dz=player.z-lastZ;distance=Math.hypot(dx,dz);
  }
  if(distance>Math.max(2.4,4*dt*5)){reset();dx=0;dz=0;distance=0}
  lastX=player.x;lastZ=player.z;
  const velocity=fly?0:clamp(distance/dt,0,3.8);
  speed=lerp(speed,velocity,1-Math.exp(-dt*6));
  mode=fly||speed<.17?'idle':speed>1.9?'fast_walk':'walk';
  if(!fly&&mode!=='idle')phase=advancePhase(phase,distance,recorded?1.46:(mode==='fast_walk'?.95:.72));
  const humanBlend=recorded?clamp((speed-.07)/.8,0,1):0;
  for(const [name,action] of Object.entries(actions)){
   const wanted=recorded?(name==='idle'?1-humanBlend:0):(name===mode?1:0);
   action.setEffectiveWeight(lerp(action.getEffectiveWeight(),wanted,1-Math.exp(-dt*11)));
   action.setEffectiveTimeScale(name==='idle'?1:clamp(speed/(name==='walk'?1.45:2.5),.3,1.8));
  }
  mixer.update(dt);
  if(recorded){
   source='CMU human motion capture 02_01';
   recorded.action.setEffectiveWeight(lerp(recorded.action.getEffectiveWeight(),humanBlend,1-Math.exp(-dt*11)));
   recorded.action.time=phase/(Math.PI*2)*recorded.data.duration_seconds;
   mixer.update(0);
   const sway=recorded.data.root_sway_xy;
   const a=phase/(Math.PI*2)*(recorded.times.length-1),i=Math.floor(a);
   const frac=a-i,j=Math.min(i+1,recorded.times.length-1),o=i*2,p=j*2;
   const weight=recorded.action.getEffectiveWeight();
   torso.position.set(torsoRest.x+lerp(sway[o],sway[p],frac)*weight,
      torsoRest.y+lerp(sway[o+1],sway[p+1],frac)*weight,torsoRest.z);
  }else{source='procedural fallback'}
  if(Number.isFinite(player.yaw)){
   if(lastFacing!==null){
    const change=Math.atan2(Math.sin(player.yaw-lastFacing),Math.cos(player.yaw-lastFacing));
    turnRate=lerp(turnRate,clamp(change/Math.max(dt,.005),-3,3),1-Math.exp(-dt*5));
   }
   lastFacing=player.yaw;
   byName.Thoracic_T7.rotation.y=clamp(-turnRate*.028,-.07,.07);
  }
  root.updateMatrixWorld(true);
  ikAccum=Math.min(ikAccum+dt,.2);
  let solves=0,corrected=0;
  // Screen-hidden first person skips IK while keeping skeletal animation.
  if(ikAccum>=1/cfg.ikHz&&active&&!fly){
   ikAccum-=1/cfg.ikHz;
   root.getWorldScale(scale);inverse.copy(root.matrixWorld).invert();
   const unit=Math.abs(scale.y)||1;
   const dirX=distance>1e-6?dx/distance:0;
   const dirZ=distance>1e-6?dz/distance:0;
   for(const foot of feet){
    neutral(foot);
    const ground=terrain.height(foot.neutral.x,foot.neutral.z);
    if(ground===null){foot.hasLock=false;continue}
    const clearance=.105*unit;
    const t=((phase/(2*Math.PI)+(foot.side>0?.5:0))%1+1)%1;
    const stance=mode==='idle'||t<.58;
    if(!foot.hasLock){
     foot.lock.copy(foot.neutral);foot.lock.y=ground+clearance;
     foot.begin.copy(foot.lock);foot.end.copy(foot.lock);
     foot.hasLock=true;foot.swing=false;
    }
    if(stance){
     if(foot.swing){foot.lock.copy(foot.end);foot.swing=false}
     foot.planted=true;foot.target.copy(foot.lock);
    }else{
     if(!foot.swing){
      foot.begin.copy(foot.lock);foot.end.copy(foot.neutral);
      foot.end.x+=dirX*.18;foot.end.z+=dirZ*.18;
      if(!pinToMeasuredSurface(foot.end,clearance))foot.end.copy(foot.begin);
      foot.swing=true;
     }
     foot.planted=false;
     const p=clamp((t-.58)/.42,0,1),sm=smoothstep(p);
     foot.target.set(lerp(foot.begin.x,foot.end.x,sm),
      lerp(foot.begin.y,foot.end.y,sm)+raisedFoot(p,cfg.footHeight*unit),
      lerp(foot.begin.z,foot.end.z,sm));
    }
    // Clamp visual IK reach, not DEM heights. Count any foot-lock corrections.
    const ddx=foot.target.x-foot.neutral.x,ddz=foot.target.z-foot.neutral.z;
    const radius=Math.hypot(ddx,ddz),max=.33*unit;
    if(radius>max){
     foot.target.x=foot.neutral.x+ddx*max/radius;
     foot.target.z=foot.neutral.z+ddz*max/radius;
     corrected++;slipCorrections++;
    }
    const normal=terrain.normal(foot.target.x,foot.target.z);
    if(recorded){
      // Preserve captured stance, swing, arm counter-rotation and knee flexion.
      // The ground IK acts only as a bounded secondary planted-foot correction.
      if(!foot.planted)continue;
      foot.priorHip.copy(foot.upper.quaternion);
      foot.priorKnee.copy(foot.lower.quaternion);
      foot.priorFoot.copy(foot.foot.quaternion);
      foot.foot.getWorldPosition(foot.sole);
      const error=foot.sole.distanceTo(foot.target);
      const mix=clamp((error-.045)/.20,0,.34);
      if(mix<.01)continue;
      if(solveFoot(foot,foot.target,normal)){
        foot.upper.quaternion.copy(foot.priorHip).slerp(foot.upper.quaternion,mix);
        foot.lower.quaternion.copy(foot.priorKnee).slerp(foot.lower.quaternion,mix);
        foot.foot.quaternion.copy(foot.priorFoot).slerp(foot.foot.quaternion,mix);
        solves++;updates++;
      }
    }else if(solveFoot(foot,foot.target,normal)){solves++;updates++}
   }
  }
  const stats=metrics.tick(dt,solves,corrected);
  if(typeof document!=='undefined'&&document.body){
   const data=document.body.dataset;
   data.astronautMotion=mode;
   data.astronautAnimationSource=source;
   data.astronautMocapTracks=String(recorded?.data.tracks.length||0);
   data.astronautMocapDuration=String(recorded?.data.duration_seconds||0);
   data.astronautHumanPose=byName.L_Femur.rotation.x.toFixed(4)+':'+byName.R_Femur.rotation.x.toFixed(4);
   data.astronautIkSolves=String(updates);
   data.astronautBones=String(bones.length);
   data.astronautRigged='true';
   data.astronautAnatomy='80 axial + 126 appendicular';
   data.astronautGaitSpeed=speed.toFixed(2);
   data.astronautSlipCorrections=String(slipCorrections);
   data.astronautIkHz=String(cfg.ikHz);
   data.astronautFpsSample=String(stats.fps);
  }
  return {mode,speedMps:speed,ikSolves:updates,slipCorrections,fpsSample:stats.fps,source};
 }
 function getState(){return {mode,speedMps:speed,ikSolves:updates,
  slipCorrections,quality:qualityName,boneCount:bones.length,source,metrics:metrics.read()}}
 function dispose(){mixer.stopAllAction();mixer.uncacheRoot(root)}
 return {update,reset,dispose,getState};
}
