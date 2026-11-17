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
 joints=[
  ('RigRoot',-1,(0,0,0)),
  ('Hips',0,(0,.95,0)),('Spine',1,(0,.28,0)),
  ('Chest',2,(0,.27,0)),('Neck',3,(0,.24,0)),
  ('Head',4,(0,.11,0)),
  ('LeftUpperLeg',1,(-.205,-.015,0)),
  ('LeftLowerLeg',6,(0,-.47,0)),('LeftFoot',7,(0,-.35,-.06)),
  ('RightUpperLeg',1,(.205,-.015,0)),
  ('RightLowerLeg',9,(0,-.47,0)),('RightFoot',10,(0,-.35,-.06)),
  ('LeftUpperArm',3,(-.29,.01,0)),
  ('LeftForearm',12,(-.045,-.32,0)),
  ('LeftHand',13,(0,-.25,0)),
  ('RightUpperArm',3,(.29,.01,0)),
  ('RightForearm',15,(.045,-.32,0)),
  ('RightHand',16,(0,-.25,0))
 ]
 world=[]
 for name,parent,local in joints:
  world.append(np.array(local)+(world[parent] if parent>=0 else 0))
 total=np.zeros((len(pos),len(joints)),dtype=np.float32)
 head=smooth(1.72,1.82,y)
 chest=smooth(1.17,1.40,y)*(1-smooth(1.66,1.83,y))
 spine=smooth(.96,1.18,y)*(1-smooth(1.42,1.58,y))
 hips=np.clip(1-head-chest-spine,0,1)
 total[:,1]=hips;total[:,2]=spine;total[:,3]=chest;total[:,5]=head
 right=smooth(-.06,.10,x)
 legMask=1-smooth(.83,.98,y)
 thigh=smooth(.43,.57,y)
 ankle=smooth(.13,.23,y)
 # Each side is assigned simultaneously, preserving both symmetric legs.
 for sign,side,bones in ((-1,1-right,(6,7,8)),(1,right,(9,10,11))):
  mask=legMask*side
  for i,f in zip(bones,(thigh,(1-thigh)*ankle,(1-thigh)*(1-ankle))):
   total[:,i]=mask*f
 total[:,1:6]*=(1-legMask)[:,None]
 armMask=smooth(.225,.34,np.abs(x))*smooth(.94,1.12,y)
 armMask*=1-smooth(1.5,1.64,y)
 armMask*=1-smooth(.12,.32,z) # Do not warp the life-support backpack.
 upper=smooth(1.19,1.30,y)
 hand=1-smooth(.98,1.08,y)
 for side,bones in ((1-right,(12,13,14)),(right,(15,16,17))):
  mask=armMask*side
  for i,f in zip(bones,(upper,(1-upper)*(1-hand),(1-upper)*hand)):
   total[:,i]=mask*f
 total[:,:12]*=(1-armMask)[:,None]
 total/=np.maximum(total.sum(axis=1,keepdims=True),1e-8)
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
  for joint in (6,7,8,9,10,11,12,13,15,16,2,3,5):
   samples=[]
   for frame in range(count+1):
    phase=2*math.pi*frame/count
    offset=0 if joint in (6,7,8,15,16) else math.pi
    sinus=math.sin(phase+offset)
    swing=max(0,-sinus)
    if joint in (6,9):value=amplitude*sinus
    elif joint in (7,10):value=-amplitude*1.05*swing
    elif joint in (8,11):value=-amplitude*.12*sinus
    elif joint in (12,15):value=-amplitude*.65*sinus
    elif joint in (13,16):value=-amplitude*.18*(.5+swing)
    elif joint==2:value=amplitude*.055*math.sin(phase*2)
    elif joint==3:value=amplitude*.08*math.sin(phase+math.pi/2)
    else:value=amplitude*.025*math.sin(phase)
    samples.append(quat_x(value))
   output=acc(np.array(samples,dtype='<f4'),'VEC4',target=None)
   idx=len(samplers)
   samplers.append({'input':timeline,'output':output,'interpolation':'LINEAR'})
   channels.append({'sampler':idx,'target':{'node':joint+1,'path':'rotation'}})
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
  'extensionsUsed':['EXT_texture_webp','KHR_materials_specular']}
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
  'joints':len(joints),'animations':[a['name'] for a in animations],
  'bytes':length,'type':'educational modified NASA Z-2 suit'},indent=2))
if __name__=='__main__':
 if len(sys.argv)!=4:sys.exit('Usage: python scripts/build_motion_asset.py source.glb decoded_dir output.glb')
 build(*sys.argv[1:])
