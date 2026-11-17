#!/usr/bin/env python3
"""Build genuinely skinned educational NASA Z-2 glTF from its ORIGINAL geometry.

NASA is the publisher of the visual suit geometry, not the independently
authored bones, weights, gait clips or IK system. No physically certified EVA.
Requires original Z2 SHA256 and the decoded Draco arrays.
"""
from __future__ import annotations
import hashlib, json, math, struct, sys
from pathlib import Path
import numpy as np
from anatomy206 import create_skeleton

EXPECTED='4199762c27f8e730030a7bf9f1a453c203457e84c33b36247c0237a74f9a0c2a'

def smooth(a,b,v):
 x=np.clip((v-a)/(b-a),0,1)
 return x*x*(3-2*x)

def build(src,decoded,dest):
 src,decoded,dest=Path(src),Path(decoded),Path(dest)
 raw=src.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:
  raise ValueError('Not the inspected NASA original Z-2 file')
 size=struct.unpack_from('<I',raw,12)[0]
 assert raw[:4]==b'glTF' and struct.unpack_from('<I',raw,4)[0]==2
 original=json.loads(raw[20:20+size])
 oldbin=raw[20+size+8:]
 vertices=np.fromfile(decoded/'z2_positions.f32',dtype='<f4').reshape(-1,3)
 normals=np.fromfile(decoded/'z2_normals.f32',dtype='<f4').reshape(-1,3)
 uv=np.fromfile(decoded/'z2_uv.f32',dtype='<f4').reshape(-1,2)
 faces=np.fromfile(decoded/'z2_faces.u32',dtype='<u4')
 if len(vertices)!=50864 or len(faces)!=92712:
  raise ValueError('NASA geometry mismatch: refusing a substituted mesh')
 # Bake NASA model node 90-degree X rotation into a Y-up humanoid.
 pos=np.stack((vertices[:,0],-vertices[:,2],vertices[:,1]),axis=1)
 nrm=np.stack((normals[:,0],-normals[:,2],normals[:,1]),axis=1)
 x,y,z=pos.T
 # Joint parent indices and parent-local rest translations in metres.
 anatomy=create_skeleton()
 boneIndex={b.name:i for i,b in enumerate(anatomy)}
 coords={b.name:np.array(b.xyz) for b in anatomy}
 joints=[(b.name,boneIndex[b.parent] if b.parent else -1,
          tuple(coords[b.name]-coords[b.parent]) if b.parent else b.xyz)
         for b in anatomy]
 assert len(joints)==206
 world=[]
 for name,parent,local in joints:
  world.append(np.array(local)+(world[parent] if parent>=0 else 0))
 # 206 anatomically named bones, but only surface joints are skin-weighted.
 # Finger phalanges remain anatomical control points where NASA's fabric
 # mesh does not separate individual fingers. Up to 4 GPU influences / vertex.
 total=np.zeros((len(pos),len(joints)),dtype=np.float32)
 head=smooth(1.72,1.83,y)
 lower=1-smooth(.88,1.02,y)
 armMask=smooth(.215,.33,np.abs(x))*smooth(.95,1.10,y)
 armMask*=1-smooth(1.55,1.69,y)
 armMask*=1-smooth(.14,.30,z)
 body=(1-lower)*(1-armMask)
 lumbar=(1-smooth(1.16,1.34,y))*(1-head)
 thorax=smooth(1.14,1.34,y)*(1-head)
 shoulders=smooth(1.44,1.58,y)
 total[:,boneIndex['Lumbar_L3']]=body*lumbar*.84
 total[:,boneIndex['Sacrum']]=body*lumbar*.16
 total[:,boneIndex['Thoracic_T7']]=body*thorax*(1-shoulders)
 total[:,boneIndex['Thoracic_T3']]=body*thorax*shoulders
 total[:,boneIndex['Cranium_Frontal']]=body*head
 right=smooth(-.07,.07,x)
 for side,w in (('L',1-right),('R',right)):
  leg=lower*w
  thigh=smooth(.425,.58,y)
  shin=(1-thigh)*smooth(.16,.28,y)
  boot=(1-thigh)*(1-smooth(.16,.28,y))
  toe=boot*smooth(-.125,-.26,-z)*smooth(.07,.13,.13-y)
  total[:,boneIndex[f'{side}_Femur']]+=leg*thigh
  total[:,boneIndex[f'{side}_Tibia']]+=leg*shin
  total[:,boneIndex[f'{side}_Tarsal_Talus']]+=leg*(boot-toe)*.68
  total[:,boneIndex[f'{side}_Metatarsal_Middle']]+=leg*(boot-toe)*.32
  total[:,boneIndex[f'{side}_ToePhalanx_Middle_Proximal']]+=leg*toe
  am=armMask*w
  upper=smooth(1.22,1.33,y)
  glove=1-smooth(.96,1.10,y)
  total[:,boneIndex[f'{side}_Humerus']]+=am*upper
  total[:,boneIndex[f'{side}_Radius']]+=am*(1-upper)*(1-glove)
  total[:,boneIndex[f'{side}_Carpal_Capitate']]+=am*(1-upper)*glove*.8
  total[:,boneIndex[f'{side}_Metacarpal_Middle']]+=am*(1-upper)*glove*.2
 norm=total.sum(axis=1)
 if np.any(norm<1e-6):raise ValueError("Unweighted NASA Z-2 suit mesh")
 total/=norm[:,None]
 # Four GPU influences per vertex; joints selected by non-zero weight.
 ids=np.argsort(total,axis=1)[:,-4:]
 weights=np.take_along_axis(total,ids,axis=1)
 weights/=np.maximum(weights.sum(axis=1,keepdims=True),1e-8)
 assert np.isfinite(weights).all()
 blob=bytearray();views=[];accessors=[]
 def view(data,target=None):
  while len(blob)%4:blob.append(0)
  offset=len(blob);blob.extend(data)
  rec={'buffer':0,'byteOffset':offset,'byteLength':len(data)}
  if target is not None:rec['target']=target
  views.append(rec)
  return len(views)-1
 def acc(arr,kind,component=5126,target=34962,bounds=False):
  v=view(np.ascontiguousarray(arr).tobytes(),target)
  rec={'bufferView':v,'componentType':component,'count':len(arr),'type':kind}
  if bounds:
   rec['min']=np.atleast_1d(np.min(arr,axis=0)).astype(float).tolist()
   rec['max']=np.atleast_1d(np.max(arr,axis=0)).astype(float).tolist()
  accessors.append(rec)
  return len(accessors)-1
 aPos=acc(pos.astype('<f4'),'VEC3',bounds=True)
 aNorm=acc(nrm.astype('<f4'),'VEC3')
 aUv=acc(uv.astype('<f4'),'VEC2')
 aFace=acc(faces.astype('<u4'),'SCALAR',5125,34963)
 aJoint=acc(ids.astype('<u2'),'VEC4',5123)
 aWeight=acc(weights.astype('<f4'),'VEC4')
 bind=np.repeat(np.eye(4,dtype=np.float32)[None,:,:],len(joints),axis=0)
 for i,loc in enumerate(world):bind[i,:3,3]=-loc
 aBind=acc(bind.transpose(0,2,1).astype('<f4').reshape(len(joints),16),'MAT4',target=None)
 def quat_x(a):return [math.sin(a/2),0,0,math.cos(a/2)]
 animations=[]
 for name,duration,count,amplitude in [('idle',2.5,20,.012),('walk',1.17,32,.34),('fast_walk',.72,28,.52)]:
  ticks=np.linspace(0,duration,count+1,dtype='<f4')
  timeline=acc(ticks,'SCALAR',target=None,bounds=True)
  samplers=[];channels=[]
  tracks={}
  for side in ('L','R'):
   tracks.update({
    f'{side}_Femur':'hip',f'{side}_Tibia':'knee',
    f'{side}_Tarsal_Talus':'ankle',
    f'{side}_Metatarsal_Middle':'toe',f'{side}_Humerus':'arm',
    f'{side}_Radius':'elbow',f'{side}_Carpal_Capitate':'wrist',
    f'{side}_Phalanx_Thumb_Proximal':'finger',
    f'{side}_Phalanx_Index_Proximal':'finger'})
  for bone in ('Lumbar_L3','Thoracic_T7','Thoracic_T3','Cervical_C4','Cranium_Frontal'):
   tracks[bone]='trunk'
  for nameOfBone,role in tracks.items():
   joint=boneIndex[nameOfBone]
   samples=[]
   for frame in range(count+1):
    phase=2*math.pi*frame/count
    sidePhase=math.pi if nameOfBone.startswith('R_') else 0
    sinus=math.sin(phase+sidePhase)
    swing=max(0,-sinus)
    if role=='hip':value=amplitude*sinus
    elif role=='knee':value=-amplitude*1.1*swing
    elif role=='ankle':value=-amplitude*.2*sinus
    elif role=='toe':value=amplitude*.08*swing
    elif role=='arm':value=-amplitude*.52*sinus
    elif role=='elbow':value=-amplitude*.12*(.5+swing)
    elif role=='wrist':value=amplitude*.04*sinus
    elif role=='finger':value=amplitude*.055*(.5+swing)
    else:value=amplitude*.04*math.sin(phase*2)
    samples.append(quat_x(value))
   output=acc(np.array(samples,dtype='<f4'),'VEC4',target=None)
   index=len(samplers)
   samplers.append({'input':timeline,'output':output,'interpolation':'LINEAR'})
   channels.append({'sampler':index,'target':{'node':joint+1,'path':'rotation'}})
  animations.append({'name':name,'samplers':samplers,'channels':channels})
 images=[]
 for im in original['images']:
  old=original['bufferViews'][im['bufferView']]
  b=oldbin[old['byteOffset']:old['byteOffset']+old['byteLength']]
  images.append({'bufferView':view(b),'mimeType':im['mimeType'],'name':im.get('name','NASA_Z2')})
 nodes=[{'name':'NASA_Z2_Animated','mesh':0,'skin':0}]
 nodes.extend({'name':name,'translation':list(local)} for name,parent,local in joints)
 for i,(_,parent,_) in enumerate(joints):
  if parent>=0:nodes[parent+1].setdefault('children',[]).append(i+1)
 while len(blob)%4:blob.append(0)
 gltf={'asset':{'version':'2.0','generator':'Mars EVA: modified NASA Z2 educational rig'},
  'scene':0,'scenes':[{'nodes':[0,1]}],'nodes':nodes,'buffers':[{'byteLength':len(blob)}],
  'bufferViews':views,'accessors':accessors,'materials':original['materials'],
  'meshes':[{'name':'NASA_Z2_Rigged','primitives':[{'attributes':{
   'POSITION':aPos,'NORMAL':aNorm,'TEXCOORD_0':aUv,
   'JOINTS_0':aJoint,'WEIGHTS_0':aWeight},
   'indices':aFace,'material':0,'mode':4}]}],
  'skins':[{'inverseBindMatrices':aBind,
   'joints':list(range(1,len(joints)+1)),'skeleton':1}],
  'animations':animations,'images':images,
  'textures':original['textures'],'samplers':original['samplers'],
  'extensionsUsed':['EXT_texture_webp','KHR_materials_specular'],
  'extras':{'anatomical_bones':206,'axial':80,'appendicular':126,
   'source':'NASA Z-2 visual geometry; independent educational rig',
   'surface_skin_weighted_bones':int(np.count_nonzero(np.max(total,axis=0)))}}
 meta=json.dumps(gltf,separators=(',',':'),ensure_ascii=False).encode()
 meta+=b' '*((-len(meta))%4)
 length=12+8+len(meta)+8+len(blob)
 dest.parent.mkdir(parents=True,exist_ok=True)
 with dest.open('wb') as f:
  f.write(struct.pack('<4sII',b'glTF',2,length))
  f.write(struct.pack('<I4s',len(meta),b'JSON'));f.write(meta)
  f.write(struct.pack('<I4s',len(blob),b'BIN\0'));f.write(blob)
 print(json.dumps({'source_sha256':EXPECTED,
  'output_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),
  'vertices':len(pos),'triangles':len(faces)//3,
  'joints':len(joints),'axial':80,'appendicular':126,
  'animated_bones':23,
  'surface_skin_weighted_bones':int(np.count_nonzero(np.max(total,axis=0))),
  'animations':[a['name'] for a in animations],
  'bytes':length,'type':'educational modified NASA Z-2 suit'},indent=2))
if __name__=='__main__':
 if len(sys.argv)!=4:sys.exit('Usage: python scripts/build_motion_asset.py source.glb decoded_dir output.glb')
 build(*sys.argv[1:])
