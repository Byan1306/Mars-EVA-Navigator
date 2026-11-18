#!/usr/bin/env python3
"""Retarget recorded CMU subject 02, clip 01 human walking to NASA Z-2 educational skeleton.

Original BVH in cmu/02_01_walk_original.zip, sha256 of decoded BVH pinned.
SciPy is a BUILD dependency only, never used by browser.
"""
from __future__ import annotations
import hashlib, json, sys, zipfile
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

EXPECTED_BVH_SHA256='cf56db43157acc3d200b3d4215523f54d354a8926bea67e1f6c8031bd335ba7e'
SOURCE='https://github.com/Shriinivas/cmubvh/blob/main/Sequence-001-009/02/Data/02_01.zip'
MAPPING={
'Hips':'Sacrum','LeftUpLeg':'L_Femur','LeftLeg':'L_Tibia',
'LeftFoot':'L_Tarsal_Talus','LeftToeBase':'L_Metatarsal_Middle',
'RightUpLeg':'R_Femur','RightLeg':'R_Tibia',
'RightFoot':'R_Tarsal_Talus','RightToeBase':'R_Metatarsal_Middle',
'LowerBack':'Lumbar_L3','Spine':'Thoracic_T7','Spine1':'Thoracic_T3',
'Neck1':'Cervical_C4','Head':'Cranium_Frontal','LeftArm':'L_Humerus',
'LeftForeArm':'L_Radius','LeftHand':'L_Carpal_Capitate',
'RightArm':'R_Humerus','RightForeArm':'R_Radius','RightHand':'R_Carpal_Capitate'}
START=157;PERIOD=130;SAMPLES=65

def read(archive):
 with zipfile.ZipFile(archive) as z:
  names=[name for name in z.namelist() if name.lower().endswith('.bvh')]
  if len(names)!=1:raise ValueError('Exactly one human-walking BVH required')
  b=z.read(names[0])
 if hashlib.sha256(b).hexdigest()!=EXPECTED_BVH_SHA256:
  raise ValueError('Unexpected/modified motion capture; preserve original provenance')
 lines=b.decode('utf-8-sig').splitlines()
 mi=next(i for i,line in enumerate(lines) if line.strip()=='MOTION')
 ch={};name=None;index=0
 for line in lines[:mi]:
  parts=line.strip().split()
  if not parts:continue
  if parts[0] in ('JOINT','ROOT'):name=parts[1]
  elif parts[0]=='CHANNELS':
   n=int(parts[1]);ch[name]={label:index+j for j,label in enumerate(parts[2:2+n])};index+=n
 frames=np.array([np.fromstring(s,sep=' ') for s in lines[mi+3:] if s.strip()],dtype=np.float64)
 frame_dt=float(lines[mi+2].split(':')[1])
 if frames.shape!=(344,96) or not .0082<frame_dt<.0085:
  raise ValueError('Unexpected original CMU 02_01 BVH structure')
 return frames,ch,frame_dt

def retarget(archive,out):
 frames,channels,dt=read(archive)
 frames_idx=START+np.arange(SAMPLES+1)*PERIOD/SAMPLES
 times=np.linspace(0,PERIOD*dt,SAMPLES+1)
 space=Rotation.from_euler('y',180,degrees=True)
 tracks=[]
 for src,target in MAPPING.items():
  ch=channels[src]
  angles=np.stack([frames[:,ch[x]] for x in ('Zrotation','Yrotation','Xrotation')],axis=1)
  if src not in ('LeftLeg','RightLeg'):
   neutral=np.median(angles[START:START+PERIOD],axis=0)
   if src in ('LeftUpLeg','RightUpLeg'):neutral[2]=0
   angles-=neutral
  else:angles[:,:2]*=.45
  r=space*Rotation.from_euler('ZYX',angles,degrees=True)*space.inv()
  weight=(.78 if 'Arm' in src else .82 if 'ForeArm' in src
   else .70 if src in ('Spine','Spine1','LowerBack','Neck1','Head') else 1)
  if weight!=1:r=Rotation.from_rotvec(r.as_rotvec()*weight)
  selected=Slerp(np.arange(len(frames)),r)(frames_idx).as_quat()
  # Blend last four samples towards first quaternion for seamless locomotion.
  for j in range(SAMPLES-4,SAMPLES):
   t=(j-SAMPLES+5)/5
   pair=Rotation.from_quat([selected[j],selected[0]])
   selected[j]=Slerp([0,1],pair)([t]).as_quat()[0]
  selected[-1]=selected[0]
  if not np.isfinite(selected).all():raise ValueError('Invalid mocap quaternion')
  tracks.append({'bone':target,'quats':np.round(selected,5).ravel().tolist()})
 root=channels['Hips']
 rest=frames[START:START+PERIOD][:,[root['Xposition'],root['Yposition']]].mean(axis=0)
 pelvis=[]
 for frame in frames_idx:
  i=min(len(frames)-2,int(frame));p=frame-i
  value=(1-p)*frames[i,:3]+p*frames[i+1,:3]
  pelvis.append(np.array([np.clip(-(value[0]-rest[0])*.035,-.035,.035),
                          np.clip((value[1]-rest[1])*.052,-.045,.045)]))
 for j in range(SAMPLES-4,SAMPLES+1):
  t=(j-SAMPLES+5)/5;pelvis[j]=pelvis[j]*(1-t)+pelvis[0]*t
 payload={'format':'MarsEVA-CMU-HumanWalk-v1',
  'origin':'Carnegie Mellon Graphics Lab Motion Capture Database',
  'source_url':SOURCE,'source_bvh_sha256':EXPECTED_BVH_SHA256,
  'source_frames':len(frames),'source_fps':round(1/dt,1),
  'cycle_start_frame':START,'cycle_frame_count':PERIOD,
  'duration_seconds':round(PERIOD*dt,6),
  'times':np.round(times,6).tolist(),
  'root_sway_xy':np.round(pelvis,5).ravel().tolist(),'tracks':tracks,
  'limitations':'Recorded human walking, educational retarget to an external NASA Z-2 suit. NOT NASA-certified EVA biomechanics.'}
 Path(out).parent.mkdir(parents=True,exist_ok=True)
 Path(out).write_text(json.dumps(payload,separators=(',',':'))+'\n')
 print(json.dumps({'source_bvh_sha256':EXPECTED_BVH_SHA256,
   'track_count':len(tracks),'samples':len(times),'duration':payload['duration_seconds']}))
 return payload

if __name__=='__main__':
 if len(sys.argv)!=3:sys.exit('Usage: python scripts/retarget_cmu_walk.py source.zip output.json')
 retarget(sys.argv[1],sys.argv[2])
