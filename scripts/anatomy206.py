"""Adult anatomical skeleton: exactly 206 bones, 80 axial + 126 appendicular.

Locations are approximate 3D animation pivots inside NASA's visible Z-2
outer spacesuit, NOT reconstructed internal bones or a real human CT scan.
The skeleton root is Sacrum; no extra non-anatomical joint is counted.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Bone:
 name:str
 parent:str|None
 xyz:tuple[float,float,float]
 group:str

def create_skeleton():
 bones=[];seen=set()
 def add(name,parent,xyz,group):
  assert name not in seen and (parent is None or parent in seen),(name,parent)
  seen.add(name)
  bones.append(Bone(name,parent,tuple(float(v) for v in xyz),group))
 add('Sacrum',None,(0,.95,0),'axial')
 add('Coccyx','Sacrum',(0,.865,.015),'axial')
 parent='Sacrum'
 for i in (5,4,3,2,1):
  n=f'Lumbar_L{i}';add(n,parent,(0,1.01+(5-i)*.055,0),'axial');parent=n
 for i in range(12,0,-1):
  n=f'Thoracic_T{i}';add(n,parent,(0,1.29+(12-i)*.026,0),'axial');parent=n
 for i in range(7,0,-1):
  n=f'Cervical_C{i}';add(n,parent,(0,1.60+(7-i)*.026,0),'axial');parent=n
 add('Cranium_Occipital',parent,(0,1.77,.1),'axial')
 for n,p in [
  ('Frontal',(0,1.876,-.065)),('Parietal_L',(-.095,1.888,.055)),
  ('Parietal_R',(.095,1.888,.055)),('Temporal_L',(-.108,1.8,.04)),
  ('Temporal_R',(.108,1.8,.04)),('Sphenoid',(0,1.81,-.025)),
  ('Ethmoid',(0,1.823,-.103))]:
  add('Cranium_'+n,'Cranium_Occipital',p,'axial')
 add('Face_Mandible','Cranium_Occipital',(0,1.755,-.105),'axial')
 add('Face_Vomer','Cranium_Ethmoid',(0,1.818,-.119),'axial')
 for side in ('L','R'):
  k=-1 if side=='L' else 1
  for n,x,y,z in [
   ('Maxilla',.042,1.79,-.114),('Palatine',.046,1.777,-.088),
   ('Zygomatic',.087,1.815,-.092),('Nasal',.032,1.845,-.135),
   ('Lacrimal',.05,1.843,-.105),('InferiorNasalConcha',.034,1.813,-.132)]:
   add(f'Face_{side}_{n}','Cranium_Frontal',(k*x,y,z),'axial')
  add(f'Ossicle_{side}_Malleus',f'Cranium_Temporal_{side}',(k*.113,1.801,.028),'axial')
  add(f'Ossicle_{side}_Incus',f'Ossicle_{side}_Malleus',(k*.120,1.802,.03),'axial')
  add(f'Ossicle_{side}_Stapes',f'Ossicle_{side}_Incus',(k*.117,1.803,.027),'axial')
 add('Hyoid','Cervical_C5',(0,1.68,-.12),'axial')
 add('Sternum','Thoracic_T6',(0,1.47,-.15),'axial')
 for i in range(1,13):
  for side in ('L','R'):
   k=-1 if side=='L' else 1
   add(f'Rib_{side}_{i:02d}',f'Thoracic_T{i}',(k*(.09+min(i,7)*.014),1.54-(i-1)*.023,-.07),'axial')
 carpal=['Scaphoid','Lunate','Triquetrum','Pisiform','Trapezium','Trapezoid','Capitate','Hamate']
 tarsal=['Talus','Calcaneus','Navicular','Cuboid','MedialCuneiform','IntermediateCuneiform','LateralCuneiform']
 digits=['Thumb','Index','Middle','Ring','Little']
 for side in ('L','R'):
  k=-1 if side=='L' else 1
  add(f'{side}_Clavicle','Thoracic_T1',(k*.16,1.565,-.03),'appendicular')
  add(f'{side}_Scapula',f'{side}_Clavicle',(k*.27,1.50,.085),'appendicular')
  add(f'{side}_Humerus',f'{side}_Scapula',(k*.32,1.49,-.013),'appendicular')
  add(f'{side}_Radius',f'{side}_Humerus',(k*.35,1.185,-.04),'appendicular')
  add(f'{side}_Ulna',f'{side}_Humerus',(k*.32,1.18,.016),'appendicular')
  for j,n in enumerate(carpal):
   add(f'{side}_Carpal_{n}',f'{side}_Radius',
    (k*(.309+(j%4)*.02),1.037+(j//4)*.015,-.028),'appendicular')
  for i,digit in enumerate(digits):
   x=k*(.303+.018*i)
   pc=['Trapezium','Trapezoid','Capitate','Capitate','Hamate'][i]
   add(f'{side}_Metacarpal_{digit}',f'{side}_Carpal_{pc}',(x,.992,-.035),'appendicular')
   parts=('Proximal','Distal') if digit=='Thumb' else ('Proximal','Middle','Distal')
   parent=f'{side}_Metacarpal_{digit}'
   for j,part in enumerate(parts):
    name=f'{side}_Phalanx_{digit}_{part}'
    add(name,parent,(x,.953-j*.026,-.058-j*.018),'appendicular');parent=name
  add(f'{side}_Hip','Sacrum',(k*.157,.94,0),'appendicular')
  add(f'{side}_Femur',f'{side}_Hip',(k*.212,.88,0),'appendicular')
  add(f'{side}_Patella',f'{side}_Femur',(k*.211,.466,-.097),'appendicular')
  add(f'{side}_Tibia',f'{side}_Femur',(k*.213,.47,0),'appendicular')
  add(f'{side}_Fibula',f'{side}_Femur',(k*.262,.445,.025),'appendicular')
  for j,n in enumerate(tarsal):
   y=.11 if n=='Talus' else (.085 if n=='Calcaneus' else .08)
   z=.025 if n=='Talus' else (.12 if n=='Calcaneus' else -.039)
   add(f'{side}_Tarsal_{n}',f'{side}_Tibia',(k*(.208+.011*(j%3)),y,z),'appendicular')
  for i,digit in enumerate(digits):
   x=k*(.15+i*.031)
   t=['MedialCuneiform','MedialCuneiform','IntermediateCuneiform','LateralCuneiform','Cuboid'][i]
   add(f'{side}_Metatarsal_{digit}',f'{side}_Tarsal_{t}',(x,.075,-.088),'appendicular')
   parts=('Proximal','Distal') if digit=='Thumb' else ('Proximal','Middle','Distal')
   parent=f'{side}_Metatarsal_{digit}'
   for j,part in enumerate(parts):
    name=f'{side}_ToePhalanx_{digit}_{part}'
    add(name,parent,(x,.07-j*.005,-.145-j*.032),'appendicular');parent=name
 assert len(bones)==206 and sum(b.group=='axial' for b in bones)==80
 assert sum(b.group=='appendicular' for b in bones)==126
 return bones
