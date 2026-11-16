#!/usr/bin/env python3
"""Unit tests with invented heights ONLY in isolated tests, never release."""
import importlib.util,json,tempfile
from pathlib import Path
import unittest
import numpy as np
from rasterio.transform import from_origin

from prepare_surface import vertices_for_tile,pack_glb

class GeometryUnitTests(unittest.TestCase):
 def test_glb_has_measured_1_to_1_heights_and_nodata_holes(self):
  grid=np.arange(257*257,dtype="float64").reshape(257,257)*.001-2500
  valid=np.ones_like(grid,dtype=bool)
  valid[30,30]=False
  trans=from_origin(1000,2000,1,1)
  p,n,uv,f=vertices_for_tile(grid,valid,trans,-2499.1,1129,1880,1,0,0,1)
  self.assertEqual(len(p),257*257)
  self.assertAlmostEqual(float(p[0,1]),-.9,places=3)
  self.assertTrue(np.isfinite(n).all())
  self.assertTrue(np.isfinite(uv).all())
  self.assertLess(len(f),2*256*256)
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/"tile.glb"
   pack_glb(path,p,n,uv,f)
   raw=path.read_bytes()
   self.assertEqual(raw[:4],b"glTF")
   self.assertEqual(int.from_bytes(raw[8:12],"little"),len(raw))
 def test_lod_preserves_boundary_points(self):
  grid=np.ones((257,257),dtype="float64")*10
  valid=np.ones_like(grid,dtype=bool)
  trans=from_origin(1000,2000,1,1)
  for step in (1,2,4,8):
   p,n,uv,f=vertices_for_tile(grid,valid,trans,10,1128,1872,1,0,0,step)
   w=256//step+1
   self.assertEqual(p.shape,(w*w,3))
   self.assertTrue(np.allclose(p[:,1],0))
   self.assertEqual(len(f),2*(w-1)*(w-1))

if __name__=="__main__":
 unittest.main()
