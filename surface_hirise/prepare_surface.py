#!/usr/bin/env python3
"""Produce a real 1024 x 1024 m Jezero HiRISE terrain package from USGS/PDS.

This workflow reads bounded windows from official GeoTIFFs using GDAL /vsicurl/.
No substitute data are ever generated. Source product hash is NOT claimed when
the upstream whole file is not downloaded; each exported derivative is hashed.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, shutil, struct, sys
from pathlib import Path

import numpy as np
from PIL import Image
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import rowcol, from_bounds, xy
from rasterio.windows import Window
from rasterio.vrt import WarpedVRT
from pyproj import Transformer

HERE=Path(__file__).resolve().parent
DEM_FILE="JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif"
ORTHO_FILE="JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first.tif"
PREFIXES=(
 "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/HiRISE/",
 "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/",
)
SOURCE_PAGES={
 "dem":"https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_dtm_mosaic",
 "ortho":"https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_orthorectified_image_mosaic",
}
MARS_GEO=CRS.from_string("+proj=longlat +R=3396190 +no_defs +type=crs")
CENTER=(77.42669,18.45938)
TILE=256
GRID=1024
IMAGE_RES=4 # 0.25m photo per projected 1m DTM interval
VALID_MIN=.95

def sha(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for block in iter(lambda:f.read(2**20),b""):h.update(block)
 return h.hexdigest()

def official(name):
 errors=[]
 for prefix in PREFIXES:
  url=prefix+name
  try:
   src=rasterio.open("/vsicurl/"+url)
   if src.count!=1 or not src.crs:
    raise ValueError("Not a single-band, georeferenced raster")
   from pyproj import CRS as PyCRS
   radius=PyCRS.from_wkt(src.crs.to_wkt()).ellipsoid.semi_major_metre
   if not 3_300_000<radius<3_500_000:
    raise ValueError("Not a Martian CRS")
   print("REMOTE_SOURCE",name,src.width,src.height,src.res,str(src.crs),url,flush=True)
   return src,url
  except Exception as ex:
   errors.append(url+": "+str(ex))
 raise RuntimeError("All official sources failed: "+" | ".join(errors))

def pack_glb(path,points,normals,uv,faces):
 # Minimal glTF 2.0 mesh; no texture or fabricated materials embedded.
 parts=[];views=[];accessors=[]
 def add(data,component,typ,count,target,minimum=None,maximum=None):
  data=np.ascontiguousarray(data)
  start=sum(len(p) for p in parts)
  pad=(-start)%4
  if pad:parts.append(b"\0"*pad);start+=pad
  raw=data.tobytes(order="C");parts.append(raw)
  view=len(views)
  views.append({"buffer":0,"byteOffset":start,"byteLength":len(raw),"target":target})
  acc={"bufferView":view,"componentType":component,"count":int(count),"type":typ}
  if minimum is not None:acc["min"]=[float(v) for v in minimum]
  if maximum is not None:acc["max"]=[float(v) for v in maximum]
  accessors.append(acc)
  return len(accessors)-1
 pa=add(points.astype("<f4"),5126,"VEC3",len(points),34962,points.min(0),points.max(0))
 na=add(normals.astype("<f4"),5126,"VEC3",len(normals),34962)
 ta=add(uv.astype("<f4"),5126,"VEC2",len(uv),34962)
 fa=add(faces.astype("<u4").ravel(),5125,"SCALAR",faces.size,34963)
 payload=b"".join(parts)
 payload+=b"\0"*((-len(payload))%4)
 model={"asset":{"version":"2.0","generator":"Mars EVA USGS HiRISE real DEM exporter"},
        "buffers":[{"byteLength":len(payload)}],"bufferViews":views,"accessors":accessors,
        "materials":[{"pbrMetallicRoughness":{"metallicFactor":0.0,"roughnessFactor":1.0},"doubleSided":False}],
        "meshes":[{"primitives":[{"attributes":{"POSITION":pa,"NORMAL":na,"TEXCOORD_0":ta},
             "indices":fa,"material":0,"mode":4}]}],
        "nodes":[{"mesh":0}],"scenes":[{"nodes":[0]}],"scene":0}
 j=json.dumps(model,separators=(",",":"),allow_nan=False).encode()
 j+=b" "*((-len(j))%4)
 output=12+8+len(j)+8+len(payload)
 with path.open("wb") as fh:
  fh.write(struct.pack("<4sII",b"glTF",2,output))
  fh.write(struct.pack("<I4s",len(j),b"JSON"));fh.write(j)
  fh.write(struct.pack("<I4s",len(payload),b"BIN\0"));fh.write(payload)

def vertices_for_tile(heights,valid,transform,ref,anchor_x,anchor_y,cos_lat,ir,ic,step):
 rows=np.arange(ir*TILE,ir*TILE+TILE+1,step,dtype=np.int32)
 cols=np.arange(ic*TILE,ic*TILE+TILE+1,step,dtype=np.int32)
 rr,cc=np.meshgrid(rows,cols,indexing="ij")
 hh=heights[rr,cc].copy()
 mask=valid[rr,cc]
 # Holes are never represented by claimed scientific geometry.
 hh[~mask]=ref
 # Affine transform sample CENTER positions, not pixel corner coordinates.
 xx=transform.c+(cc+.5)*transform.a+(rr+.5)*transform.b
 yy=transform.f+(cc+.5)*transform.d+(rr+.5)*transform.e
 points=np.stack([(xx-anchor_x)*cos_lat,hh-ref,anchor_y-yy],axis=-1).astype("float32")
 # Normals are derived from the observed DEM; finite neighbour differences only.
 di=np.gradient(hh,axis=0)
 dj=np.gradient(hh,axis=1)
 dx=abs(transform.a)*cos_lat*step; dz=abs(transform.e)*step
 slope_x=dj/max(dx,1e-6);slope_z=di/max(dz,1e-6)
 normals=np.stack([-slope_x,np.ones_like(hh),-slope_z],axis=-1)
 normals/=np.maximum(np.linalg.norm(normals,axis=-1,keepdims=True),1e-12)
 # Each tile's UV maps the corresponding 256 m x 256 m orthoimage.
 u=(cc-ic*TILE)/TILE;v=1-(rr-ir*TILE)/TILE
 uv=np.stack([u,v],axis=-1).astype("float32")
 w=rr.shape[1]
 faces=[]
 for r in range(w-1):
  for c in range(w-1):
   # Check ALL source DEM pixels within the coarse quad. Avoid bridging NoData at LOD.
   r0=int(rows[r]);r1=int(rows[r+1]);c0=int(cols[c]);c1=int(cols[c+1])
   if not np.all(valid[r0:r1+1,c0:c1+1]):continue
   a=r*w+c;b=a+1;d=(r+1)*w+c;e=d+1
   faces.append((a,d,b));faces.append((b,d,e))
 faces=np.asarray(faces,dtype=np.uint32).reshape(-1,3)
 if faces.size==0:raise ValueError(f"Tile {ir},{ic} has no valid measured faces")
 return points.reshape(-1,3),normals.astype("float32").reshape(-1,3),uv.reshape(-1,2),faces

def generate(out,center_lon,center_lat,ortho_enabled=True,tiles_per_side=4):
 out=out.resolve();out.mkdir(parents=True,exist_ok=True)
 if tiles_per_side not in (1,2,4):raise ValueError("Tile count must be 1, 2, or 4")
 grid=tiles_per_side*TILE
 with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",CPL_VSIL_CURL_USE_HEAD="YES",
    GDAL_HTTP_MAX_RETRY="2",GDAL_HTTP_RETRY_DELAY="3",GDAL_HTTP_TIMEOUT="60",
    GDAL_HTTP_MULTIRANGE="YES",GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES"):
  src,dem_url=official(DEM_FILE)
  try:
   forward=Transformer.from_crs(MARS_GEO,src.crs,always_xy=True)
   inverse=Transformer.from_crs(src.crs,MARS_GEO,always_xy=True)
   px,py=forward.transform(center_lon,center_lat)
   cr,cc=rowcol(src.transform,px,py)
   row0=cr-grid//2;col0=cc-grid//2
   if row0<0 or col0<0 or row0+grid+1>src.height or col0+grid+1>src.width:
    raise ValueError("Requested HiRISE area extends outside source raster")
   window=Window(col0,row0,grid+1,grid+1)
   raw=src.read(1,window=window,masked=True)
   heights=np.asarray(raw.data,dtype="float64")
   good=(~np.ma.getmaskarray(raw))&np.isfinite(heights)&(np.abs(heights)<100000)
   coverage=float(good.mean())
   if coverage<VALID_MIN:raise ValueError(f"HiRISE DEM coverage only {coverage:.2%}; aborting")
   trans=src.window_transform(window)
   mid=grid//2
   ref=float(heights[mid,mid])
   if not np.isfinite(ref):raise ValueError("Invalid center reference elevation")
   anchor_x,anchor_y=xy(trans,mid,mid,offset="center")
   angle=math.cos(math.radians(center_lat))
   lon_w,lat_s=inverse.transform(*xy(trans,grid,0,offset="center"))
   lon_e,lat_n=inverse.transform(*xy(trans,0,grid,offset="center"))
   # Explicit source native sample spacing (map-projected, not ground-truth accuracy).
   x_native=abs(src.res[0]);y_native=abs(src.res[1])
   if not (.5<=x_native<=2 and .5<=y_native<=2):
    raise ValueError(f"HiRISE original DTM is not ~1m/post: {src.res}")
   print("REAL_DEM",f"{grid+1}x{grid+1}","valid",coverage,"ref_m",ref,flush=True)
   ortho=None;ortho_url=None;image=None;ortho_coverage=None
   if ortho_enabled:
    try:
     ortho,ortho_url=official(ORTHO_FILE)
     left=trans.c+.5*trans.a
     top=trans.f+.5*trans.e
     right=left+grid*trans.a
     bottom=top+grid*trans.e
     # Destination samples cover the exact same projected extent as DEM vertices.
     texture_grid=grid*IMAGE_RES
     ortho_transform=from_bounds(left,bottom,right,top,texture_grid,texture_grid)
     with WarpedVRT(ortho,crs=src.crs,transform=ortho_transform,
          width=texture_grid,height=texture_grid,resampling=Resampling.bilinear) as view:
      image_masked=view.read(1,masked=True)
     ortho_data=image_masked.data
     visual_mask=(~np.ma.getmaskarray(image_masked))&np.isfinite(ortho_data)
     ortho_coverage=float(visual_mask.mean())
     if ortho_coverage<VALID_MIN:
      raise ValueError(f"Orthoimage has only {ortho_coverage:.1%} valid pixels")
     if ortho_data.dtype!=np.uint8:
      lo,hi=np.percentile(ortho_data[visual_mask],[1,99])
      image=np.clip((ortho_data.astype("float32")-lo)/max(1,hi-lo)*255,0,255).astype("uint8")
      image_method=f"Display stretch 1st-99th percentiles ({lo:.2f},{hi:.2f})"
     else:
      image=ortho_data.astype("uint8")
      image_method="Identity for original 8-bit grayscale values"
     image[~visual_mask]=0
     print("REAL_ORTHO",image.shape,"coverage",ortho_coverage,flush=True)
    except Exception as exc:
     print("REAL_ORTHO_NOT_AVAILABLE",str(exc),flush=True)
     ortho=None;image=None
   for folder in ("assets/tiles","assets/textures","assets/masks","reports"):
    (out/folder).mkdir(parents=True,exist_ok=True)
   rendered=[]
   for ir in range(tiles_per_side):
    for ic in range(tiles_per_side):
     tag=f"r{ir}_c{ic}"
     entry={"id":tag,"row":ir,"col":ic,"kind":"HiRISE DTM", "lods":[],
            "texture":None,"mask":None,"region_m":[ic*TILE,ir*TILE,TILE,TILE]}
     validity=good[ir*TILE:ir*TILE+TILE+1,ic*TILE:ic*TILE+TILE+1]
     mask_path=f"assets/masks/{tag}.png"
     Image.fromarray((validity*255).astype("uint8")).save(out/mask_path)
     entry["mask"]=mask_path
     for lod in (1,2,4,8):
      pts,norm,uv,faces=vertices_for_tile(
          heights,good,trans,ref,anchor_x,anchor_y,angle,ir,ic,lod)
      rel=f"assets/tiles/{tag}_lod{lod}.glb"
      pack_glb(out/rel,pts,norm,uv,faces)
      entry["lods"].append({"step":lod,"path":rel,
        "vertices":int(pts.shape[0]),"triangles":int(faces.shape[0]),
        "sha256":sha(out/rel)})
     if image is not None:
      im=image[ir*TILE*IMAGE_RES:(ir+1)*TILE*IMAGE_RES,
               ic*TILE*IMAGE_RES:(ic+1)*TILE*IMAGE_RES]
      rel=f"assets/textures/{tag}_hirise_25cm.png"
      Image.fromarray(im).save(out/rel,optimize=True)
      entry["texture"]={"path":rel,"resolution_projected_m_per_px":.25,
                        "width":int(im.shape[1]),"height":int(im.shape[0]),
                        "sha256":sha(out/rel)}
     rendered.append(entry)
   manifest={
    "schema_version":"1.0","status":"measured terrain, independently derived from official USGS GeoTIFF",
    "region":"Jezero Crater, Mars",
    "center_lon_lat_east_north":[center_lon,center_lat],
    "geographic_bbox_lonlat":[lon_w,lat_s,lon_e,lat_n],
    "projected_crs":src.crs.to_string(),"source_dem":dem_url,
    "source_dem_metadata":SOURCE_PAGES["dem"],"source_dem_sha256_full":None,
    "source_dem_hash_note":"Original entire 1.8GB file was not downloaded; no original whole-file SHA-256 is claimed.",
    "source_dem_native_pixel_spacing_projected_m":[x_native,y_native],
    "rendered_vertex_spacing_projected_m":x_native,
    "elevation_unit":"m","elevation_reference_m":ref,
    "reference_definition":"DEM center sample, physical heights minus this number",
    "local_coordinate_system":"X east; Y up (relative to center DEM elevation); Z south",
    "east_scale_factor":angle,
    "geometry_scale_y":1.0,"no_data_handling":"No synthetic heights. NoData faces omitted even in coarse LOD.",
    "vertical_source_uncertainty":"Not evaluated beyond native USGS metadata; do not claim certified precision.",
    "photographic_texture":{"source":ortho_url if image is not None else None,
      "metadata":SOURCE_PAGES["ortho"],"available":image is not None,
      "native_spacing_projected_m":.25 if image is not None else None,
      "coverage_fraction":ortho_coverage,"image_method":image_method if image is not None else None,
      "source_whole_file_sha256":None},
    "dimensions_m_projected":[grid*x_native,grid*y_native],
    "tile_cells":TILE,"tiles":rendered,
    "scientific_vs_visual":"HiRISE terrain + ortho are observed/derived USGS data; ambient lighting/colors are illustrative.",
    "limitations":["No rover-stereo rocks or sub-metre collision geometry",
       "1m samples do not guarantee 1m absolute horizontal or vertical positional accuracy",
       "Projection x scale adjusted by cos(latitude) for Mars-local metres",
       "Edges with NoData are omitted, not filled",
       "Distant regional CTX terrain must be added separately for large horizon"] }
   (out/"terrain_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
   (out/"reports"/"validation.json").write_text(json.dumps({
      "dem_source":dem_url,"ortho_source":ortho_url,"full_orig_sha256_verified":False,
      "elevation_bounds_m":[float(heights[good].min()),float(heights[good].max())],
      "dem_coverage":coverage,"ortho_coverage":ortho_coverage,
      "center_sample_elevation_m":ref,
      "max_raw_nan_or_invalid":int(np.size(good)-good.sum()),
      "shared_border_max_m":max(
        float(np.max(np.abs(heights[k*TILE,:]-heights[k*TILE,:]))) for k in range(1,tiles_per_side))
        if tiles_per_side>1 else 0.0,
      "output_tiles":len(rendered),"output_lod_meshes":sum(len(t["lods"]) for t in rendered)
     },indent=2)+"\n")
   for f in ("README.md","terrain_loader.mjs","preview.html"):
    shutil.copy2(HERE/f,out/f)
   print("REAL_SURFACE_READY",str(out),"tiles",len(rendered),"texture",image is not None,flush=True)
  finally:
   src.close()
   if "ortho" in locals() and ortho is not None:ortho.close()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--output",type=Path,required=True)
 parser.add_argument("--center-lon",type=float,default=CENTER[0])
 parser.add_argument("--center-lat",type=float,default=CENTER[1])
 parser.add_argument("--tiles",type=int,choices=[1,2,4],default=4)
 parser.add_argument("--no-ortho",action="store_true")
 args=parser.parse_args()
 generate(args.output,args.center_lon,args.center_lat,not args.no_ortho,args.tiles)
if __name__=="__main__":main()
