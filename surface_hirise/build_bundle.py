#!/usr/bin/env python3
"""Copy exact local Three.js ESM files to standalone scientific web preview."""
import argparse,shutil,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(out):
 out=Path(out).resolve()
 if not (out/"terrain_manifest.json").is_file():
  raise FileNotFoundError("Cannot publish: missing official DEM terrain_manifest.json.")
 base=ROOT/"node_modules"/"three"
 files={
  "build/three.module.js":"vendor/three.module.js",
  "build/three.core.js":"vendor/three.core.js",
  "examples/jsm/loaders/GLTFLoader.js":"vendor/loaders/GLTFLoader.js",
  "examples/jsm/utils/BufferGeometryUtils.js":"vendor/utils/BufferGeometryUtils.js"}
 for s,d in files.items():
  src=base/s;dst=out/d
  if not src.is_file():raise FileNotFoundError(f"npm install required: {s}")
  dst.parent.mkdir(parents=True,exist_ok=True)
  shutil.copy2(src,dst)
 # Include reproducible processing code without any raw full-size GeoTIFF.
 (out/"scripts").mkdir(exist_ok=True)
 for f in ("prepare_surface.py","validate_output.py","build_bundle.py","test_geometry.py"):
  shutil.copy2(Path(__file__).parent/f,out/"scripts"/f)
 print("HIRES_BUNDLE_READY",out)
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("dir",type=Path)
 args=p.parse_args()
 build(args.dir)
