"""No false anatomy claim: exactly 80 axial + 126 appendicular = 206 adult bones."""
import unittest
from scripts.anatomy206 import create_skeleton

class AdultAnatomyRigTests(unittest.TestCase):
 def setUp(self):
  self.bones=create_skeleton()
  self.names=[b.name for b in self.bones]
  self.by_name={b.name:b for b in self.bones}
 def test_exact_adult_anatomical_counts(self):
  self.assertEqual(len(self.bones),206)
  self.assertEqual(len(self.names),len(set(self.names)))
  self.assertEqual(sum(b.group=='axial' for b in self.bones),80)
  self.assertEqual(sum(b.group=='appendicular' for b in self.bones),126)
 def test_spine_ribs_cranium_ossicles_hyoid(self):
  for name in ['Sacrum','Coccyx','Hyoid','Sternum',
    'Cranium_Frontal','Cranium_Occipital','Face_Mandible']:
   self.assertIn(name,self.by_name)
  for i in range(1,13):
   for side in ('L','R'):self.assertIn(f'Rib_{side}_{i:02d}',self.by_name)
  for side in ('L','R'):
   for name in ('Malleus','Incus','Stapes'):
    self.assertIn(f'Ossicle_{side}_{name}',self.by_name)
 def test_each_hand_and_foot_has_full_named_phalanges(self):
  for side in ('L','R'):
   for digit in ('Thumb','Index','Middle','Ring','Little'):
    for part in (('Proximal','Distal') if digit=='Thumb' else
                 ('Proximal','Middle','Distal')):
     self.assertIn(f'{side}_Phalanx_{digit}_{part}',self.by_name)
     self.assertIn(f'{side}_ToePhalanx_{digit}_{part}',self.by_name)
 def test_single_hierarchical_root_with_no_cycles(self):
  self.assertEqual([b.name for b in self.bones if b.parent is None],['Sacrum'])
  for bone in self.bones:
   seen=set();current=bone
   while current.parent is not None:
    self.assertNotIn(current.name,seen)
    seen.add(current.name)
    self.assertIn(current.parent,self.by_name)
    current=self.by_name[current.parent]
 def test_pivots_are_finite(self):
  import math
  for bone in self.bones:
   self.assertEqual(len(bone.xyz),3)
   self.assertTrue(all(math.isfinite(v) for v in bone.xyz))
if __name__=='__main__':unittest.main()
