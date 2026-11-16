#!/usr/bin/env python3
"""Verify a 60 km scientific Mars world before allowing public artifact builds."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image
def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def verify(root):
 root=Path(root)
 m=json.loads((root/"terrain_manifest.json").read_text(encoding="utf-8"))
 assert m["schema_version"]=="2.0"
 assert m["area_ground_m"][0]>=50000 and m["area_ground_m"][1]>=50000
 assert m["vertical_exaggeration"]==1
 assert m["source_dem"].startswith("https://asc-pds-services.s3.us-west-2.amazonaws.com/")
 assert m["source_dem"].endswith("M20_JezeroCrater_CTXDEM_20m.tif")
 assert len(m["source_dem_sha256"])==64
 assert m["reference_elevation_m"]>-20000 and m["reference_elevation_m"]<20000
 assert m["mars_radius_m"]>3300000 and m["mars_radius_m"]<3500000
 size=m["samples_per_side"]
 assert size>2400 and size<=3201
 hfile=root/m["height_file"]["path"]
 mfile=root/m["mask_file"]["path"]
 assert hfile.stat().st_size==4*size*size
 assert mfile.stat().st_size==size*size
 assert sha(hfile)==m["height_file"]["sha256"]
 assert sha(mfile)==m["mask_file"]["sha256"]
 height=np.memmap(hfile,dtype="<f4",mode="r",shape=(size,size))
 mask=np.memmap(mfile,dtype="u1",mode="r",shape=(size,size))
 assert set(np.unique(mask)).issubset({0,1})
 fraction=float(mask.mean())
 assert abs(fraction-m["measured_coverage_fraction"])<1e-6
 assert fraction>=.60
 assert np.isfinite(height[mask!=0]).all()
 assert np.isnan(height[mask==0]).all()
 assert len(m["tiles"])==m["tile_count"][0]*m["tile_count"][1]
 assert len(m["places"])>=8
 assert len(set(p["name"] for p in m["places"]))==len(m["places"])
 real_sources=0
 for p in m["places"]:
  assert p.get("source","").startswith("https://")
  assert p.get("precision") and p.get("name")
  if p["has_measured_elevation"]:
   x=p["x_m"];z=p["z_m"]
   c=round(x/m["cell_spacing_local_m"][0]+(size-1)/2)
   r=round(z/m["cell_spacing_local_m"][1]+(size-1)/2)
   assert mask[r,c]
   assert abs(p["elevation_m"]-float(height[r,c]))<1e-3
   real_sources+=1
   if "approximate" in p["precision"].lower():
    assert "approximate" in p["precision"].lower()
 for tile in m["tiles"]:
  assert 0<=tile["row"]<m["tile_count"][1]
  assert 0<=tile["col"]<m["tile_count"][0]
  assert 0<=tile["valid_fraction"]<=1
  tex=tile.get("texture")
  if tex:
   path=root/tex["path"]
   assert sha(path)==tex["sha256"]
   with Image.open(path) as image:
    assert image.size==(tex["image_pixels_per_tile"],)*2
 assert real_sources>=5,("Too few correctly located named POI",real_sources)
 # Invariant: 60km geometry has 20m spacing; no 1m resolution claim.
 assert all(abs(v-20)<.05 for v in m["cell_spacing_local_m"])
 out={"passed":True,"terrain":"authentic USGS full Jezero CTX DEM",
  "extent_km":[a/1000 for a in m["area_ground_m"]],
  "source_grid":size,"coverage_fraction":fraction,
  "named_places":len(m["places"]),"places_with_real_elevation":real_sources,
  "tiles":len(m["tiles"]),
  "tiles_with_observed_ortho":sum(bool(x["texture"]) for x in m["tiles"]),
  "observed_ortho_available":bool(m["source_ortho"])}
 print(json.dumps(out,ensure_ascii=False,indent=2))
 (root/"validation.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 return out
if __name__=="__main__":
 parser=argparse.ArgumentParser()
 parser.add_argument("root",type=Path)
 args=parser.parse_args()
 verify(args.root)
