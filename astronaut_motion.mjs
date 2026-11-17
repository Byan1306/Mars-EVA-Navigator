/* Mars EVA Astronaut Motion Genesis.
 * NASA Z-2 mesh modified with independently authored educational skeletal rig.
 * Foot placement uses measured DEM height. Suit motion is not a certified NASA EVA gait.
 */
export function createAstronautMotion({THREE,root,gltf,sampleGround,quality='balanced'}) {
 const skin=[];root.traverse(n=>{if(n.isSkinnedMesh)skin.push(n);});
 if(!skin.length)throw Error('Z-2 humanoid needs a SkinnedMesh');
 const bones=skin[0].skeleton.bones;
 const byName=Object.fromEntries(bones.map(b=>[b.name,b]));
 for(const name of ['L_Femur','R_Femur','L_Tibia','R_Tibia',
   'L_Tarsal_Talus','R_Tarsal_Talus','L_Humerus','R_Humerus',
   'Sacrum','Lumbar_L3','Thoracic_T7'])
  if(!byName[name])throw Error('Missing rigged bone '+name);
 const mixer=new THREE.AnimationMixer(root),actions={};
 for(const clip of gltf.animations){
  if(['idle','walk','fast_walk'].includes(clip.name)){
   actions[clip.name]=mixer.clipAction(clip).setLoop(THREE.LoopRepeat).play();
   actions[clip.name].setEffectiveWeight(clip.name==='idle'?1:0);
  }
 }
 if(!actions.walk||!actions.fast_walk||!actions.idle)
  throw Error('NASA Z-2 educational rig missing locomotion clips');
 if(bones.length!==206)throw Error('Expected exactly 206 anatomical joints, received '+bones.length);
 const feet=[{side:-1,upper:byName.L_Femur,lower:byName.L_Tibia,
   foot:byName.L_Tarsal_Talus,lock:new THREE.Vector3(),begin:new THREE.Vector3(),
   end:new THREE.Vector3(),active:false,swing:false},
 {side:1,upper:byName.R_Femur,lower:byName.R_Tibia,
   foot:byName.R_Tarsal_Talus,lock:new THREE.Vector3(),begin:new THREE.Vector3(),
   end:new THREE.Vector3(),active:false,swing:false}];
 const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
 const smooth=v=>v*v*(3-2*v);
 const point=new THREE.Vector3(),target=new THREE.Vector3(),scale=new THREE.Vector3();
 const bonesCount=bones.length;
 let phase=0,speed=0,lastX=NaN,lastZ=NaN,updates=0,mode='idle';
 function ground(x,z){const v=sampleGround(x,z);return Number.isFinite(v)?v:null}
 function localFoot(side,lead=0){
   point.set(side*.205,.115,-.06+lead);
   return root.localToWorld(point);
 }
 function solve(leg,worldPosition){
   target.copy(worldPosition);root.worldToLocal(target);
   const dy=target.y-.88,dz=target.z;
   const L1=.41,L2=Math.hypot(.36,.06);
   const distance=clamp(Math.hypot(dy,dz),Math.abs(L1-L2)+.01,L1+L2-.002);
   const ray=Math.atan2(-dz,-dy);
   const hipAngle=clamp(ray-Math.acos(clamp((L1*L1+distance*distance-L2*L2)/
     (2*L1*distance),-1,1)),-1.15,1.15);
   const kneeAngle=clamp(Math.acos(clamp((distance*distance-L1*L1-L2*L2)/
     (2*L1*L2),-1,1)),0,1.7);
   leg.upper.rotation.x=hipAngle;
   leg.lower.rotation.x=kneeAngle;
   leg.upper.rotation.z=clamp((leg.side*.205-target.x)*.7,-.13,.13);
   leg.foot.rotation.x=clamp(-hipAngle-kneeAngle,-.6,.6);
   updates++;
 }
 function reset(){
   phase=0;speed=0;lastX=NaN;lastZ=NaN;
   feet.forEach(f=>{f.active=false;f.swing=false;});
 }
 function update({dt,player,active=true,fly=false,quality:nextQuality=quality}){
   quality=nextQuality;
   const distance=Number.isFinite(lastX)?Math.hypot(player.x-lastX,player.z-lastZ):0;
   const teleport=distance>4;
   if(teleport)reset();
   lastX=player.x;lastZ=player.z;
   const measuredSpeed=(dt>0&&dt<.1&&!teleport&&!fly)?clamp(distance/dt,0,4):0;
   speed+=(measuredSpeed-speed)*clamp(dt*7,0,1);
   mode=speed>.17&&!fly?(speed>1.85?'fast_walk':'walk'):'idle';
   for(const [key,action] of Object.entries(actions)){
     const current=action.getEffectiveWeight(),wanted=key===mode?1:0;
     action.setEffectiveWeight(clamp(current+(wanted-current)*dt*8,0,1));
     action.setEffectiveTimeScale(key==='idle'?1:
       clamp(speed/(key==='fast_walk'?2.55:1.45),.45,1.8));
   }
   mixer.update(dt);
   if(mode!=='idle')phase+=distance/(mode==='fast_walk'?.95:.72)*Math.PI*2;
   if(phase>1000)phase%=Math.PI*2;
   root.updateMatrixWorld(true);
   // True articulated two-bone knees + stable world-space foot targets.
   if(active&&!fly){
     root.getWorldScale(scale);
     const unit=Math.abs(scale.y)||1;
     for(const f of feet){
       const fraction=((phase/(Math.PI*2)+(f.side===1?.5:0))%1+1)%1;
       const planted=fraction<.58||mode==='idle';
       const base=localFoot(f.side);const h=ground(base.x,base.z);
       if(h===null){f.active=false;continue;}
       target.copy(base);target.y=h+.115*unit;
       if(!f.active){f.lock.copy(target);f.begin.copy(target);f.active=true;}
       if(!planted){
         if(!f.swing){
           f.begin.copy(f.lock);f.swing=true;
           f.end.copy(localFoot(f.side,.31*Math.max(.3,speed/1.45)));
           const landing=ground(f.end.x,f.end.z);
           f.end.y=(landing===null?h:landing)+.115*unit;
         }
         const t=clamp((fraction-.58)/.42,0,1);
         f.lock.set(
           f.begin.x+(f.end.x-f.begin.x)*smooth(t),
           f.begin.y+(f.end.y-f.begin.y)*smooth(t)+Math.sin(Math.PI*t)*.13*unit,
           f.begin.z+(f.end.z-f.begin.z)*smooth(t));
       }else{
         if(f.swing)f.lock.copy(f.end);
         f.swing=false;
       }
       // Prevent hyperextension across NoData boundaries and abrupt teleport.
       const neutral=localFoot(f.side);
       const dx=f.lock.x-neutral.x,dz=f.lock.z-neutral.z,r=Math.hypot(dx,dz);
       const max=.28*unit;
       if(r>max){
         const k=max/r;f.lock.x=neutral.x+dx*k;f.lock.z=neutral.z+dz*k;
       }
       solve(f,f.lock);
     }
   }
   document.body.dataset.astronautMotion=mode;
   document.body.dataset.astronautIkSolves=String(updates);
   document.body.dataset.astronautBones=String(bonesCount);
   document.body.dataset.astronautAnatomy='80 axial + 126 appendicular';
   document.body.dataset.astronautRigged='true';
   return {mode,speedMps:measuredSpeed,ikSolves:updates};
 }
 function dispose(){mixer.stopAllAction();mixer.uncacheRoot(root);}
 return {update,reset,dispose,
   getState:()=>({mode,speedMps:speed,boneCount:bonesCount,ikUpdates:updates})};
}
