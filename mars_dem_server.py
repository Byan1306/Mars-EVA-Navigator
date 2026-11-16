"""Servidor local del prototipo. Ejecutar: python mars_dem_server.py.
Dependencias: pip install fastapi uvicorn rasterio numpy
DEM: jezero_hirise_dtm.tif junto a este archivo o variable MARS_DEM_PATH.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
import math
import os

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
HTML_NAME = 'mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html'
MARS_RADIUS_M = 3396190.0
# Spherical geographic coordinates; not falsely advertised as a specific IAU datum.
MARS_LONLAT_CRS = f'+proj=longlat +R={MARS_RADIUS_M:.0f} +no_defs'


def encontrar_tif() -> Path:
    configured = os.environ.get('MARS_DEM_PATH')
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.is_file():
            raise HTTPException(404, 'MARS_DEM_PATH no apunta a un archivo existente.')
        return path
    candidates = sorted(p for p in BASE_DIR.iterdir() if p.suffix.lower() in ('.tif', '.tiff') and p.is_file())
    named = [p for p in candidates if p.stem.lower() == 'jezero_hirise_dtm']
    if len(named) == 1:
        return named[0]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise HTTPException(404, 'Falta jezero_hirise_dtm.tif. Colócalo junto al servidor o configura MARS_DEM_PATH.')
    raise HTTPException(422, 'Hay varios GeoTIFF: selecciona el DEM con MARS_DEM_PATH; no se elige por tamaño.')


def validar_raster(src) -> None:
    if src.crs is None:
        raise HTTPException(422, 'El raster no tiene CRS.')
    if src.count != 1 or src.dtypes[0] in ('uint8', 'int8'):
        raise HTTPException(422, 'Se requiere un DEM de una banda numérica de más de 8 bits, no una imagen RGB.')
    if src.width < 2 or src.height < 2:
        raise HTTPException(422, 'El DEM debe tener al menos 2 × 2 píxeles.')
    try:
        # Reject terrestrial or unknown bodies before PROJ reprojection.
        from pyproj import CRS as ProjCRS
        radius = ProjCRS.from_wkt(src.crs.to_wkt()).ellipsoid.semi_major_metre
        if not 3_300_000 < radius < 3_500_000:
            raise HTTPException(422, 'El CRS no corresponde a un cuerpo de tamaño marciano.')
    except ImportError:
        # Rasterio/PROJ itself rejects differing celestial bodies in reproject.
        if 'mars' not in src.crs.to_wkt().lower() and '3396190' not in src.crs.to_wkt():
            raise HTTPException(422, 'No se pudo identificar el CRS marciano; instala pyproj para validarlo.')
    if src.scales[0] != 1 or src.offsets[0] != 0:
        raise HTTPException(422, 'El DEM usa escala/offset. Convierte primero sus alturas a metros físicos.')
    units = src.units[0]
    if units and units.lower() not in ('m', 'meter', 'metre', 'meters', 'metres'):
        raise HTTPException(422, 'La banda de altura debe estar en metros.')


def bounds_marcianos(src):
    b = list(transform_bounds(src.crs, MARS_LONLAT_CRS, *src.bounds, densify_pts=21))
    if b[0] >= 180:
        b[0] -= 360
        b[2] -= 360
    if not all(math.isfinite(x) for x in b) or b[0] >= b[2] or b[1] >= b[3] or b[0] < -180 or b[2] > 180:
        raise HTTPException(422, 'Cobertura inválida o cruce del antimeridiano no soportado.')
    return b


@asynccontextmanager
async def lifespan(_: FastAPI):
    print('Mars EVA Navigator: http://127.0.0.1:8000 — DEM configurable con MARS_DEM_PATH')
    yield


app = FastAPI(title='Mars EVA Navigator — servidor de terreno', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[
    'http://localhost:8000', 'http://127.0.0.1:8000',
    'http://localhost:8080', 'http://127.0.0.1:8080',
], allow_methods=['GET'], allow_headers=['*'])


@app.middleware('http')
async def evitar_cache_obsoleto(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/', include_in_schema=False)
def pagina():
    path = BASE_DIR / 'open_world.html'
    if not path.is_file():
        path = BASE_DIR / HTML_NAME
    if not path.is_file():
        path = BASE_DIR / 'index.html'
    if not path.is_file():
        raise HTTPException(404, f'Coloca {HTML_NAME} o index.html junto al servidor.')
    return FileResponse(path, media_type='text/html')



# Only explicitly reviewed public 3D assets are served; no directory traversal.
@app.get('/open_world.html', include_in_schema=False)
def open_world_page():
    return FileResponse(BASE_DIR / 'open_world.html', media_type='text/html')

@app.get('/open_world.css', include_in_schema=False)
def open_world_styles():
    return FileResponse(BASE_DIR / 'open_world.css', media_type='text/css')

@app.get('/open_world.mjs', include_in_schema=False)
def open_world_code():
    return FileResponse(BASE_DIR / 'open_world.mjs', media_type='text/javascript')

@app.get('/open_world_core.js', include_in_schema=False)
def open_world_core():
    return FileResponse(BASE_DIR / 'open_world_core.js', media_type='text/javascript')

@app.get('/vendor/three.module.js', include_in_schema=False)
def world_three_vendor():
    path = BASE_DIR / 'node_modules' / 'three' / 'build' / 'three.module.js'
    if not path.is_file():
        raise HTTPException(404, 'Ejecuta npm install para instalar Three.js.')
    return FileResponse(path, media_type='text/javascript')

@app.get('/vendor/three.core.js', include_in_schema=False)
def world_three_core_vendor():
    path = BASE_DIR / 'node_modules' / 'three' / 'build' / 'three.core.js'
    if not path.is_file():
        raise HTTPException(404, 'Ejecuta npm install para instalar Three.js.')
    return FileResponse(path, media_type='text/javascript')

@app.get('/jezero_ortho_meta.json', include_in_schema=False)
def ortho_metadata():
    path = BASE_DIR / 'jezero_ortho_meta.json'
    if not path.is_file():
        raise HTTPException(404, 'La ortofoto opcional todavía no existe.')
    return FileResponse(path, media_type='application/json')

@app.get('/jezero_ortho.jpg', include_in_schema=False)
def ortho_image():
    path = BASE_DIR / 'jezero_ortho.jpg'
    if not path.is_file():
        raise HTTPException(404, 'La ortofoto opcional todavía no existe.')
    return FileResponse(path, media_type='image/jpeg')

@app.get('/' + HTML_NAME, include_in_schema=False)
def original_eva_planner():
    return FileResponse(BASE_DIR / HTML_NAME, media_type='text/html')

# Serve only explicit, public app assets. Do not expose the local DEM, database,
# credentials or private files with a generic static-directory mount.
@app.get('/curiosity_explorer.js', include_in_schema=False)
def curiosity_javascript():
    path = BASE_DIR / 'curiosity_explorer.js'
    if not path.is_file():
        raise HTTPException(404, 'Falta curiosity_explorer.js.')
    return FileResponse(path, media_type='application/javascript')


@app.get('/curiosity_explorer.css', include_in_schema=False)
def curiosity_styles():
    path = BASE_DIR / 'curiosity_explorer.css'
    if not path.is_file():
        raise HTTPException(404, 'Falta curiosity_explorer.css.')
    return FileResponse(path, media_type='text/css')


# Curiosity Mission Control: only these public assets are exposed.
@app.get('/curiosity_pro.css', include_in_schema=False)
def curiosity_professional_styles():
    path = BASE_DIR / 'curiosity_pro.css'
    if not path.is_file():
        raise HTTPException(404, 'Falta curiosity_pro.css.')
    return FileResponse(path, media_type='text/css')


@app.get('/curiosity_360_renderer.js', include_in_schema=False)
def curiosity_panorama_renderer():
    path = BASE_DIR / 'curiosity_360_renderer.js'
    if not path.is_file():
        raise HTTPException(404, 'Falta curiosity_360_renderer.js.')
    return FileResponse(path, media_type='application/javascript')


@app.get('/jezero_dem_precomputed.json', include_in_schema=False)
def static_science_dem():
    """Make a locally generated, reviewed JSON available without exposing the GeoTIFF."""
    path = BASE_DIR / 'jezero_dem_precomputed.json'
    if not path.is_file():
        raise HTTPException(404, 'No public precomputed Jezero DEM has been generated.')
    return FileResponse(path, media_type='application/json')


@app.get('/api/status')
def estado():
    """Never report a malformed/terrestrial raster as an active Mars DEM."""
    try:
        path = encontrar_tif()
        with rasterio.open(path) as src:
            validar_raster(src)
            bounds = bounds_marcianos(src)
            return {
                'status': 'activo',
                'tif_detectado': path.name,
                'crs': src.crs.to_string(),
                'full_bbox': bounds,
                'source_width': src.width,
                'source_height': src.height,
                'source_resolution': list(src.res),
                'science_status': 'DEM georreferenciado validado; no certifica seguridad EVA',
            }
    except HTTPException as exc:
        status = 'sin_dem' if exc.status_code == 404 else 'dem_invalido'
        return {'status': status, 'tif_detectado': None, 'detail': exc.detail}
    except (rasterio.errors.RasterioError, ValueError, OSError) as exc:
        return {'status': 'dem_invalido', 'tif_detectado': None,
                'detail': 'El archivo encontrado no supera la validación del DEM.'}


@app.get('/api/dem/jezero')
def obtener_dem(
    min_lon: Optional[float] = Query(None, ge=-180, le=180),
    min_lat: Optional[float] = Query(None, ge=-90, le=90),
    max_lon: Optional[float] = Query(None, ge=-180, le=180),
    max_lat: Optional[float] = Query(None, ge=-90, le=90),
    size: int = Query(110, ge=40, le=440),
):
    requested = (min_lon, min_lat, max_lon, max_lat)
    if any(v is not None for v in requested):
        if not all(v is not None and math.isfinite(v) for v in requested):
            raise HTTPException(422, 'Envía los cuatro límites finitos del recorte.')
        if min_lon >= max_lon or min_lat >= max_lat:
            raise HTTPException(422, 'Los mínimos deben ser menores que los máximos.')
    path = encontrar_tif()
    try:
        with rasterio.open(path) as src:
            validar_raster(src)
            full = bounds_marcianos(src)
            bbox = full.copy() if min_lon is None else [max(full[0], min_lon), max(full[1], min_lat), min(full[2], max_lon), min(full[3], max_lat)]
            if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                raise HTTPException(422, 'El recorte no intersecta el DEM.')
            transform = rasterio.transform.from_bounds(*bbox, size, size)
            dst = np.full((size, size), np.nan, dtype=np.float32)
            reproject(source=rasterio.band(src, 1), destination=dst,
                      src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                      dst_transform=transform, dst_crs=MARS_LONLAT_CRS, dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
            # Reproject masks separately: interpolation must not bridge unmapped holes.
            from rasterio.vrt import WarpedVRT
            with WarpedVRT(src, crs=MARS_LONLAT_CRS, transform=transform,
                           width=size, height=size, resampling=Resampling.nearest) as vrt:
                mask = vrt.read_masks(1)
            # Exclude undeclared sentinel values as well as explicit NoData.
            invalid = (mask == 0) | ~np.isfinite(dst) | (np.abs(dst) > 1e6)
            dst[invalid] = np.nan
            valid = np.isfinite(dst)
            if not valid.any():
                raise HTTPException(422, 'El recorte no contiene alturas válidas.')
            m_per_deg = math.pi * MARS_RADIUS_M / 180
            cell_x = (bbox[2]-bbox[0])/size*m_per_deg*math.cos(math.radians((bbox[1]+bbox[3])/2))
            cell_y = (bbox[3]-bbox[1])/size*m_per_deg
            source_projected = src.crs.is_projected
            source_resolution_m = [value * src.crs.linear_units_factor[1] for value in src.res] if source_projected else [
                abs(src.res[0])*m_per_deg*math.cos(math.radians((bbox[1]+bbox[3])/2)),
                abs(src.res[1])*m_per_deg,
            ]
            # Resolution is sampling spacing, not a guarantee of obstacle detection.
            downsample = max(cell_x/max(source_resolution_m[0],1e-9), cell_y/max(source_resolution_m[1],1e-9))
            return {
                'source_file': path.name, 'source_crs': src.crs.to_string(),
                'crs': MARS_LONLAT_CRS, 'coordinate_order': 'longitude, latitude',
                'elevation_units': 'm', 'units_assumed': not bool(src.units[0]),
                'pixel_registration': 'area', 'resampling': 'bilinear',
                'source_width': src.width, 'source_height': src.height,
                'source_resolution': list(src.res),
                'source_resolution_m_approx': source_resolution_m,
                'downsampling_factor_approx': downsample,
                'resolution_note': 'La malla puede omitir obstáculos subcelda; interpolar no añade detalle.',
                'requested_bbox': list(requested) if min_lon is not None else None,
                'width': size, 'height': size, 'bbox': bbox, 'full_bbox': full,
                'cell_size_m': (cell_x+cell_y)/2, 'cell_size_x_m': cell_x, 'cell_size_y_m': cell_y,
                'valid_fraction': float(valid.mean()), 'nodata_cells': int((~valid).sum()),
                'elevations': [float(v) if np.isfinite(v) else None for v in dst.ravel()],
            }
    except HTTPException:
        raise
    except (rasterio.errors.RasterioError, ValueError) as exc:
        raise HTTPException(422, 'No se pudo leer o reproyectar el DEM. Comprueba CRS, banda y archivo.') from exc


@app.get('/api/weather/analog')
def weather_analog(lat: float = Query(..., ge=-90, le=90),
                   lon: float = Query(..., ge=-180, le=180)):
    from datetime import datetime, timezone
    import httpx
    user = os.environ.get('METEOMATICS_USER')
    password = os.environ.get('METEOMATICS_PASSWORD')
    if not user or not password:
        raise HTTPException(503, 'Configura las credenciales Meteomatics en el servidor.')
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f'https://api.meteomatics.com/{timestamp}/t_2m:C,msl_pressure:hPa,wind_speed_10m:ms/{lat:.4f},{lon:.4f}/json'
    try:
        response = httpx.get(url, auth=(user, password), timeout=9, follow_redirects=False)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, 'El proveedor meteorológico no devolvió una respuesta válida.')


# Local catalog is initialized once. Updates are transactional through catalog_store.py.
from catalog_store import Catalog, MISSIONS
import json
CATALOG_PATH = BASE_DIR / 'catalog.sqlite'
if not CATALOG_PATH.exists():
    Catalog(CATALOG_PATH).replace(json.loads((BASE_DIR / 'catalog_seed.json').read_text(encoding='utf-8')))

@app.get('/api/catalog')
def get_catalog(mission: str = 'Perseverance'):
    if mission not in MISSIONS: raise HTTPException(422, 'Misión desconocida')
    return {'records': Catalog(CATALOG_PATH).list(mission)}

@app.get('/api/photos/nearby')
def nearby_photos(mission: str, lat: float = Query(...,ge=-90,le=90), lon: float = Query(...,ge=-180,le=180), radius: float = Query(500,gt=0,le=100000)):
    if mission not in MISSIONS: raise HTTPException(422, 'Misión desconocida')
    return {'records': Catalog(CATALOG_PATH).nearby(mission,lat,lon,radius)}

@app.get('/api/traverse')
def traverse(mission: str = 'Perseverance'):
    if mission not in MISSIONS: raise HTTPException(422, 'Misión desconocida')
    return {'stations': sorted(Catalog(CATALOG_PATH).list(mission,'station'),key=lambda r:r['sol']),
            'continuity': 'Discrete documented positions; no interpolated path'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
