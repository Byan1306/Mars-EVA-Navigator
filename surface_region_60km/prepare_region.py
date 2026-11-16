#!/usr/bin/env python3
"""Build a 60 x 60 km measured Jezero CTX terrain, official 2021 USGS mosaic.

No synthetic topography. High-resolution 1m HiRISE stays a separate patch with
its own datum until verified joint registration; do NOT blend elevations by eye.
"""
from __future__ import annotations
import argparse, hashlib, json, math, shutil
from pathlib import Path
from urllib.request import Request, urlopen
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import Window
from rasterio.vrt import WarpedVRT
from pyproj import CRS, Transformer
from PIL import Image

ROOT=Path(__file__).resolve().parent
PRODUCT_BASE="https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/"
DEM_FILE="M20_JezeroCrater_CTXDEM_20m.tif"
PHOTO_FILE="M20_JezeroCrater_CTXortho_mosaic_5m.tif"
DEM_URL=PRODUCT_BASE+DEM_FILE
PHOTO_URL=PRODUCT_BASE+PHOTO_FILE
USGS_REFERENCE="https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic"
CENTER_LON=77.56
CENTER_LAT=18.45
KM=60000
GRID=3000
TILE=250
TEXTURE_SIZE=1024
TILE_COUNT=GRID//TILE

# Official Gazetteer centers or clearly marked approximate mission locations.
# Segment anchors for extended geographic features come from USGS polyline
# vertices; such anchors are NOT called the official center coordinates.
SITES=[
 {"id":"jezero","name":"Cráter Jezero","type":"crater","lon":77.69,"lat":18.41,
  "precision":"IAU official centre","source":"https://planetarynames.wr.usgs.gov/Feature/Jezero",
  "detail":"Cráter de impacto de ~47,5 km de diámetro; el marcador indica su centro oficial."},
 {"id":"landing","name":"Octavia E. Butler","type":"mission","lon":77.4508,"lat":18.4447,
  "precision":"published touchdown position","source":"https://www.benweiss.mit.edu/s/Farley_2022_Science.pdf",
  "detail":"Lugar de aterrizaje de Perseverance, 18 de febrero de 2021."},
 {"id":"belva","name":"Cráter Belva","type":"crater","lon":77.38,"lat":18.48,
  "precision":"IAU official centre","source":"https://planetarynames.wr.usgs.gov/Feature/15872",
  "detail":"Cráter de aproximadamente 900 metros junto al delta occidental de Jezero."},
 {"id":"neretva","name":"Neretva Vallis","type":"valley","lon":77.20,"lat":18.55,
  "precision":"IAU official centre","source":"https://planetarynames.wr.usgs.gov/Feature/15879",
  "detail":"Antiguo valle fluvial que alimentó la zona del delta occidental."},
 {"id":"sava","name":"Sava Vallis · sector sur","type":"valley","lon":77.48585,"lat":18.85062,
  "precision":"approximate representative point on USGS named geometry",
  "source":"https://planetarynames.wr.usgs.gov/Feature/15904",
  "detail":"Parte meridional del sistema Sava Vallis; no es su centro geográfico."},
 {"id":"pliva","name":"Pliva Vallis · entrada","type":"valley","lon":78.081618,"lat":18.531017,
  "precision":"representative point on USGS named geometry",
  "source":"https://planetarynames.wr.usgs.gov/Feature/15903",
  "detail":"Extremo occidental del valle de salida Pliva Vallis."},
 {"id":"jezero-mons","name":"Jezero Mons · borde","type":"mountain","lon":78.015218,"lat":18.102069,
  "precision":"representative polygon boundary vertex, not summit",
  "source":"https://planetarynames.wr.usgs.gov/Feature/16005",
  "detail":"Punto de su límite occidental según la geometría del nomenclátor USGS."},
 {"id":"three-forks","name":"Three Forks","type":"mission","lon":77.4082,"lat":18.4528,
  "precision":"approximate mission-area anchor, not surveyed site centre",
  "source":"https://mars.nasa.gov/mars2020/mission/science/where-is-the-rover/",
  "detail":"Zona del depósito de muestras de Perseverance. Ancla aproximada."},
 {"id":"seitah","name":"Séítah","type":"geology","lon":77.4430,"lat":18.4339,
  "precision":"approximate rover-visit anchor, not official polygon centroid",
  "source":"https://ntrs.nasa.gov/api/citations/20230016438/downloads/Crumpler%20et%20al%202023%20JGR%20Planets%20Mapping%20of%20Jezero.pdf",
  "detail":"Unidad geológica explorada por Perseverance durante su campaña inicial."},
 {"id":"delta","name":"Frente del delta","type":"geology","lon":77.4061,"lat":18.4589,
  "precision":"approximate rover-visit anchor, not official polygon centroid",
  "source":"https://science.nasa.gov/mission/mars-2020-perseverance/",
  "detail":"Área del frente del antiguo delta occidental de Jezero."},
]

def sha(path:Path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()

def download(url:str,destination:Path):
 if destination.exists() and destination.stat().st_size>1024:
  return destination
 destination.parent.mkdir(parents=True,exist_ok=True)
 partial=destination.with_name(destination.name+".part")
 with urlopen(Request(url,headers={"User-Agent":"Mars-EVA-Navigator-2026"}),timeout=90) as response,partial.open("wb") as out:
  length=response.headers.get("Content-Length")
  got=0
  while True:
   part=response.read(1024*1024)
   if not part:break
   out.write(part);got+=len(part)
  if length and int(length)!=got:raise OSError("Incomplete official data download")
 if partial.stat().st_size<1024:raise OSError("Official file too small")
 partial.replace(destination)
 print("DOWNLOADED",url,destination.stat().st_size,flush=True)
 return destination

def validate_mars(src):
 if src.crs is None or src.count<1:
  raise ValueError("Source needs a georeferenced raster")
 radius=CRS.from_wkt(src.crs.to_wkt()).ellipsoid.semi_major_metre
 if not 3_300_000<radius<3_500_000:
  raise ValueError("Source CRS is not Mars")
 return radius

def terrain(output:Path,src_path:Path,texture:Path|None):
 output.mkdir(parents=True,exist_ok=True)
 size=GRID+1
 with rasterio.open(src_path) as src:
  radius=validate_mars(src)
  geo=src.crs.geodetic_crs
  forward=Transformer.from_crs(geo,src.crs,always_xy=True)
  backward=Transformer.from_crs(src.crs,geo,always_xy=True)
  xc,yc=forward.transform(CENTER_LON,CENTER_LAT)
  coslat=math.cos(math.radians(CENTER_LAT))
  target_transform=from_bounds(xc-KM/2/coslat,yc-KM/2,
             xc+KM/2/coslat,yc+KM/2,size,size)
  data=np.full((size,size),np.nan,np.float32)
  reproject(source=rasterio.band(src,1),destination=data,
    src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,
    dst_transform=target_transform,dst_crs=src.crs,dst_nodata=np.nan,
    resampling=Resampling.bilinear)
  with WarpedVRT(src,crs=src.crs,transform=target_transform,width=size,
      height=size,resampling=Resampling.nearest) as view:
   mask=view.read_masks(1)>0
  good=mask & np.isfinite(data)&(np.abs(data)<100000)
  coverage=float(good.mean())
  if coverage<.60:raise ValueError("Cannot certify 60km terrain: valid coverage "+str(coverage))
  data[~good]=np.nan
  ref=float(data[GRID//2,GRID//2])
  if not np.isfinite(ref):
   validpoints=np.argwhere(good)
   nearest=validpoints[np.argmin(np.sum((validpoints-GRID//2)**2,axis=1))]
   ref=float(data[nearest[0],nearest[1]])
  (output/"assets").mkdir(exist_ok=True)
  heights=output/"assets"/"height_ctx_20m.f32"
  masks=output/"assets"/"mask_ctx.bin"
  data.astype("<f4").tofile(heights)
  good.astype("u1").tofile(masks)
  stepx=KM/GRID
  stepz=KM/GRID
  levels=np.percentile(data[good],[2,98])
  print("REGIONAL_MEASURED",size,coverage,"height-range",
     float(np.nanmin(data)),float(np.nanmax(data)),flush=True)
  tiles=[]
  with rasterio.open(texture) if texture else _NullRaster() as photo:
   if texture:validate_mars(photo)
   for r in range(TILE_COUNT):
    for c in range(TILE_COUNT):
     name=f"r{r:02d}_c{c:02d}"
     tile={"id":name,"row":r,"col":c,"texture":None,
       "valid_fraction":float(good[r*TILE:r*TILE+TILE+1,c*TILE:c*TILE+TILE+1].mean())}
     if texture:
      area=Window(c*TILE,r*TILE,TILE+1,TILE+1)
      bounds=rasterio.windows.bounds(area,target_transform)
      tform=from_bounds(*bounds,TEXTURE_SIZE,TEXTURE_SIZE)
      pixels=np.zeros((TEXTURE_SIZE,TEXTURE_SIZE),np.float32)
      reproject(source=rasterio.band(photo,1),destination=pixels,
        src_transform=photo.transform,src_crs=photo.crs,src_nodata=photo.nodata,
        dst_transform=tform,dst_crs=src.crs,dst_nodata=np.nan,
        resampling=Resampling.bilinear)
      valid=np.isfinite(pixels)
      if valid.mean()>.45:
       lo,hi=np.percentile(pixels[valid],[1,99])
       image=np.clip((pixels-lo)*255/max(hi-lo,1),0,255).astype("uint8")
       image[~valid]=0
       dest=output/"assets"/"textures"/(name+".jpg")
       dest.parent.mkdir(parents=True,exist_ok=True)
       Image.fromarray(image,mode="L").save(dest,quality=89,optimize=True)
       tile["texture"]={"path":"assets/textures/"+dest.name,
          "coverage":float(valid.mean()),"sha256":sha(dest),
          "image_pixels_per_tile":TEXTURE_SIZE,
          "approx_resolution_ground_m":KM/TILE_COUNT/TEXTURE_SIZE}
     tiles.append(tile)
  output_sites=[]
  for site in SITES:
   site=site.copy()
   px,py=forward.transform(site["lon"],site["lat"])
   x=(px-xc)*coslat;z=yc-py
   site["x_m"]=float(x);site["z_m"]=float(z)
   ic=int(round(x/stepx+GRID/2));ir=int(round(z/stepz+GRID/2))
   site["inside_region"]=bool(0<=ic<=GRID and 0<=ir<=GRID)
   site["has_measured_elevation"]=bool(site["inside_region"] and good[ir,ic])
   site["elevation_m"]=float(data[ir,ic]) if site["has_measured_elevation"] else None
   output_sites.append(site)
  pwest,psouth=backward.transform(xc-KM/2/coslat,yc-KM/2)
  peast,pnorth=backward.transform(xc+KM/2/coslat,yc+KM/2)
  manifest={
   "schema_version":"2.0",
   "area_ground_m":[KM,KM],"tile_count":[TILE_COUNT,TILE_COUNT],
   "source_dem":DEM_URL,"source_url":USGS_REFERENCE,"source_ortho":PHOTO_URL if texture else None,
   "origin_lon_lat":[CENTER_LON,CENTER_LAT],
   "geographic_bbox":[pwest,psouth,peast,pnorth],
   "projection_crs":src.crs.to_string(),
   "mars_radius_m":radius,"x_scale_cos_lat":coslat,
   "source_dem_nominal_pixel_m":20,"source_ortho_nominal_pixel_m":5,
   "samples_per_side":size,"cell_spacing_local_m":[stepx,stepz],
   "source_dem_sha256":sha(src_path),"source_ortho_sha256":sha(texture) if texture else None,
   "measured_coverage_fraction":coverage,"validity_threshold":.60,
   "elevation_unit":"m","reference_elevation_m":ref,"vertical_exaggeration":1,
   "grid_order":"north to south, west to east, pixel centers",
   "height_file":{"path":"assets/height_ctx_20m.f32","sha256":sha(heights)},
   "mask_file":{"path":"assets/mask_ctx.bin","sha256":sha(masks)},
   "tiles":tiles,"places":output_sites,
   "scientific_status":"source measured derived elevations; named point precision varies by USGS or NASA evidence",
   "detail_note":"60km regional CTX. 1m HiRISE only in separate 1km authenticated module; do not label entire 60km as 1m.",
   "limitations":["20m nominal source resolution; 60km grid spacing 20m local, source equirectangular pixel spacing differs by latitude",
      "NoData excluded and not filled; locations with unmeasured height cannot be teleported to",
      "Source GeoTIFF processed by GDAL reproject with bilinear DEM interpolation",
      "Image stretch is illustrative, not natural-colour Mars photograph",
      "Approximate mission anchors are not certified exact rover georeferencing",
      "HiRISE patch separately referenced until vertical datum and elevation offsets are validated"]
  }
  (output/"terrain_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
  (output/"places.json").write_text(json.dumps(output_sites,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
  print("REGIONAL_READY",KM,"x",KM,"m",len(tiles),"tiles",len(output_sites),"places",flush=True)
  return manifest

class _NullRaster:
 def __enter__(self):return None
 def __exit__(self,*exc):return False

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--output",type=Path,default=Path("_region60km/Jezero_60km"))
 p.add_argument("--cache",type=Path,default=Path("_region60km/downloads"))
 p.add_argument("--no-photo",action="store_true")
 args=p.parse_args()
 src=download(DEM_URL,args.cache/DEM_FILE)
 photo=None
 if not args.no_photo:
  try:photo=download(PHOTO_URL,args.cache/PHOTO_FILE)
  except Exception as exc:print("CTX_PHOTO_UNAVAILABLE",exc,flush=True)
 terrain(args.output,src,photo)

if __name__=="__main__":main()
