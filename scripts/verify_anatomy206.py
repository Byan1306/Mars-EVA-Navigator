#!/usr/bin/env python3
"""Verify 206-bone NASA Z-2 educational animation glTF (source integrity is separately pinned)."""
import json,struct,sys,math
from pathlib import Path
import numpy as np
from anatomy206 import create_skeleton

def verify(path):
 b=Path(path).read_bytes()
 if b[:4]!=b'glTF' or len(b)!=struct.unpack_from('<I',b,8)[0]:
  raise ValueError('Invalid glTF binary header')
 jlen=struct.unpack_from('<I',b,12)[0]
 j=json.loads(b[20:20+jlen])
 bins=20+jlen+8
 if b[bins-4:bins]!=b'BIN\0':raise ValueError('No binary glTF chunk')
 bones=create_skeleton()
 assert len(j['skins'])==1 and len(j['skins'][0]['joints'])==206
 joint_nodes=j['skins'][0]['joints']
 names=[j['nodes'][i]['name'] for i in joint_nodes]
 assert len(set(names))==206
 assert names==[bone.name for bone in bones]
 assert len([bone for bone in bones if bone.group=='axial'])==80
 assert len([bone for bone in bones if bone.group=='appendicular'])==126
 assert j['skins'][0]['skeleton']==joint_nodes[0]
 for i,bone in enumerate(bones):
  if bone.parent:
   p=names.index(bone.parent)
   assert joint_nodes[i] in j['nodes'][joint_nodes[p]].get('children',[])
 accessors=j['accessors']
 def a(index):
  item=accessors[index]
  view=j['bufferViews'][item['bufferView']]
  ty={5126:'<f4',5125:'<u4',5123:'<u2'}[item['componentType']]
  size={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[item['type']]
  start=bins+view.get('byteOffset',0)+item.get('byteOffset',0)
  data=np.frombuffer(b,dtype=ty,count=item['count']*size,offset=start)
  return data.reshape(item['count'],size)
 prim=j['meshes'][0]['primitives'][0]
 verts=a(prim['attributes']['POSITION'])
 assert verts.shape==(50864,3)
 assert a(prim['indices']).shape==(30904*3,1)
 indices=a(prim['attributes']['JOINTS_0'])
 weights=a(prim['attributes']['WEIGHTS_0'])
 assert indices.shape==(50864,4)
 assert weights.shape==(50864,4)
 assert np.all(indices>=0) and np.all(indices<206)
 assert np.all(np.isfinite(weights)) and np.all(weights>=0)
 assert np.max(np.abs(weights.sum(axis=1)-1))<2e-6
 bind=a(j['skins'][0]['inverseBindMatrices'])
 assert bind.shape==(206,16) and np.isfinite(bind).all()
 clips={c['name']:c for c in j['animations']}
 assert set(clips)=={'idle','walk','fast_walk'}
 moving=set()
 for clip in clips.values():
  assert len(clip['channels'])>=20
  for channel in clip['channels']:
   assert channel['target']['node'] in joint_nodes
   assert channel['target']['path']=='rotation'
   moving.add(j['nodes'][channel['target']['node']]['name'])
 for essential in ['L_Femur','R_Femur','L_Tibia','R_Tibia',
     'L_Tarsal_Talus','R_Tarsal_Talus','L_Humerus','R_Humerus']:
  assert essential in moving
 report={'passed':True,'anatomical_bones':206,'axial':80,'appendicular':126,
   'vertices':len(verts),'triangles':30904,'clip_count':len(clips),
   'animated_bones':len(moving),'deforming_bones':len(set(indices[weights>1e-6].ravel().tolist())),
   'skin_influences_per_vertex':4}
 print(json.dumps(report,indent=2));return report

if __name__=='__main__':
 if len(sys.argv)!=2:sys.exit('Usage: python scripts/verify_anatomy206.py model.glb')
 verify(sys.argv[1])
