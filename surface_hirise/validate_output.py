#!/usr/bin/env python3
"""Independent checks on delivered authentic HiRISE GLB tiles (no source raster needed)."""
import argparse,hashlib,json,math,struct,sys
from pathlib import Path
import numpy as np
from PIL import Image

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()

def glb_positions(path):
 data=path.read_bytes()
 magic,version,length=struct.unpack_from("<4sII",data,0)
 assert magic==b"glTF" and version==2 and length==len(data),str(path)
 length_j,magic_j=struct.unpack_from("<I4s",data,12)
 assert magic_j==b"JSON"
 j=json.loads(data[20:20+length_j])
 length_bin,magic_bin=struct.unpack_from("<I4s",data,20+length_j)
 assert magic_bin==b"BIN\0"
 bin_offset=20+length_j+8
 primitive=j["meshes"][0]["primitives"][0]
 acc=j["accessors"][primitive["attributes"]["POSITION"]]
 view=j["bufferViews"][acc["bufferView"]]
 start=bin_offset+view.get("byteOffset",0)+acc.get("byteOffset",0)
 count=acc["count"]
 pts=np.frombuffer(data,dtype="<f4",count=count*3,offset=start).reshape(-1,3)
 return pts,j

def validate(root):
 root=Path(root)
 m=json.loads((root/"terrain_manifest.json").read_text())
 assert m["elevation_unit"]=="m" and m["geometry_scale_y"]==1
 assert m["source_dem"].startswith("https://")
 assert "HiRISE" in m["source_dem"] and "JEZ" in m["source_dem"]
 assert m["source_dem_sha256_full"] is None
 n=m["height_file"]["samples_per_side"]
 data_path=root/m["height_file"]["path"]
 mask_path=root/m["mask_file"]["path"]
 assert data_path.stat().st_size==4*n*n
 assert mask_path.stat().st_size==n*n
 assert sha(data_path)==m["height_file"]["sha256"]
 assert sha(mask_path)==m["mask_file"]["sha256"]
 heights=np.fromfile(data_path,dtype="<f4").reshape(n,n)
 mask=np.fromfile(mask_path,dtype="u1").reshape(n,n)>0
 assert np.isfinite(heights[mask]).all()
 coverage=float(mask.mean())
 assert coverage>.94
 ref=m["elevation_reference_m"]
 count=0;max_yerr=0.;max_xerr=0.
 first_by_col={};first_by_row={}
 stepX,stepZ=m["local_sample_spacing_m"]
 x0,z0=m["local_sample_center_origin_m"]
 for entry in m["tiles"]:
  r=entry["row"];c=entry["col"]
  for lod in entry["lods"]:
   path=root/lod["path"]
   assert sha(path)==lod["sha256"]
   pts,gltf=glb_positions(path)
   step=lod["step"]
   w=256//step+1
   assert len(pts)==w*w and lod["vertices"]==len(pts)
   assert lod["triangles"]>0
   for ir,ic in ((0,0),(w//2,w//2),(w-1,w-1)):
    pixel_r=r*256+ir*step
    pixel_c=c*256+ic*step
    if not mask[pixel_r,pixel_c]:continue
    p=pts[ir*w+ic]
    expected_y=float(heights[pixel_r,pixel_c])-ref
    expected_x=x0+pixel_c*stepX
    expected_z=z0+pixel_r*stepZ
    max_yerr=max(max_yerr,abs(float(p[1])-expected_y))
    max_xerr=max(max_xerr,abs(float(p[0])-expected_x),
                 abs(float(p[2])-expected_z))
   count+=1
  if entry["texture"]:
   tex=entry["texture"]
   image=Image.open(root/tex["path"])
   assert image.size==(1024,1024)
   assert sha(root/tex["path"])==tex["sha256"]
  imask=Image.open(root/entry["mask"]).convert("L")
  assert imask.size==(257,257)
 assert max_yerr<.002 and max_xerr<.006,(max_yerr,max_xerr)
 assert count==len(m["tiles"])*4
 # A single source height grid backs both sides of every tile: no seam in LOD1.
 t=int(round(math.sqrt(len(m["tiles"]))))
 assert t*t==len(m["tiles"])
 max_vertical_jump=0.
 for i in range(1,t):
  for j in range(t):
   upper=heights[(i-1)*256:i*256+1,j*256:j*256+257][-1,:]
   lower=heights[i*256:(i+1)*256+1,j*256:j*256+257][0,:]
   max_vertical_jump=max(max_vertical_jump,
      float(np.nanmax(np.abs(upper-lower))))
 for j in range(1,t):
  for i in range(t):
   left=heights[i*256:i*256+257,(j-1)*256:j*256+1][:,-1]
   right=heights[i*256:i*256+257,j*256:j*256+257][:,0]
   max_vertical_jump=max(max_vertical_jump,
      float(np.nanmax(np.abs(left-right))))
 assert max_vertical_jump<.00001,max_vertical_jump
 print(json.dumps({"passed":True,"tiles":len(m["tiles"]),
  "lod_meshes_verified":count,"coverage":coverage,
  "max_vertex_y_error_m":max_yerr,
  "max_vertex_xz_error_m":max_xerr,
  "max_shared_boundary_difference_m":max_vertical_jump,
  "authentic_25cm_ortho":m["photographic_texture"]["available"]},indent=2))

if __name__=="__main__":
 ap=argparse.ArgumentParser()
 ap.add_argument("folder",type=Path)
 args=ap.parse_args()
 validate(args.folder)
