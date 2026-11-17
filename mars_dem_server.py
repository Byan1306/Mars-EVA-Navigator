"""Servidor local del prototipo. Ejecutar: python mars_dem_server.py.
Dependencias: pip install fastapi uvicorn rasterio numpy
DEM: jezero_hirise_dtm.tif junto a este archivo o variable MARS_DEM_PATH.
"""
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional
import hashlib
import json
import math
import os

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds, transform as transform_coords
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
HTML_NAME = 'mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html'
MARS_RADIUS_M = 3396190.0
# Spherical geographic coordinates; not falsely advertised as a specific IAU datum.
MARS_LONLAT_CRS = f'+proj=longlat +R={MARS_RADIUS_M:.0f} +no_defs'
OFFICIAL_DEM_PATHS = {
    'usgs_ctx': 'CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif',
    'usgs_hirise': 'HiRISE/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif',
}
USGS_BASE = 'https://planetarymaps.usgs.gov/mosaic/mars2020_trn/'
USGS_MIRROR_BASE = 'https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/'
# Observed bytes of the official CTX download, not a checksum published by USGS.
PINNED_CTX_SHA256 = '16a1aa66c3f48c1bca252795827db7b417876217aff0f5e1aff18027fab2327b'


def _file_key(path):
    stat = path.stat()
    return str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


@lru_cache(maxsize=8)
def _sha256(path, size, mtime_ns, ctime_ns):
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(2 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def procedencia_dem(path):
    """Verify recorded download provenance; CRS alone never proves authenticity."""
    manifest = path.with_suffix(path.suffix + '.provenance.json')
    if not manifest.is_file():
        return {'verified': False, 'source_url': None, 'attribution': None,
                'detail': 'Archivo local sin manifiesto de descarga verificable.'}
    try:
        record = json.loads(manifest.read_text(encoding='utf-8'))
        legacy = 'source_product' not in record and 'dataset' in record
        if legacy:
            # Earlier releases recorded retrieval URLs but no timestamp. Preserve
            # that absence instead of fabricating a new download event.
            record = record | {
                'source_product': 'usgs_' + record['dataset'],
                'source_url': record['origin_url'],
                'retrieved_url': record['download_url'],
                'attribution': record.get('source_institution'),
                'downloaded_at': None,
            }
        product_path = OFFICIAL_DEM_PATHS[record['source_product']]
        source_url = USGS_BASE + product_path
        if record['source_url'] != source_url:
            raise ValueError('Unknown source URL')
        retrieved_url = record.get('retrieved_url', source_url)
        if retrieved_url not in (source_url, USGS_MIRROR_BASE + product_path):
            raise ValueError('Unknown retrieval URL')
        if not record.get('attribution') or (not legacy and not record.get('downloaded_at')):
            raise ValueError('Incomplete provenance')
        if record['source_product'] == 'usgs_ctx' and record['sha256'] != PINNED_CTX_SHA256:
            raise ValueError('CTX content differs from the reviewed official product')
        if record['sha256'] != _sha256(*_file_key(path)):
            raise ValueError('Checksum mismatch')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, 'Procedencia DEM inválida: comprueba el manifiesto y SHA-256 del GeoTIFF.') from exc
    return {key: record[key] for key in ('source_url', 'attribution', 'sha256',
                                         'source_product', 'downloaded_at', 'doi',
                                         'authors', 'product_page', 'vertical_reference',
                                         'checksum_note', 'native_resolution_m') if key in record} | {
        'verified': True, 'retrieved_url': retrieved_url,
        'content_pinned': record['source_product'] == 'usgs_ctx',
        'download_time_recorded': bool(record.get('downloaded_at')),
        'verification_method': 'official_download_manifest_and_local_sha256',
        'verification_note': 'Hash de integridad local; no es una firma ni un checksum publicado por USGS.',
    }


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
    if src.driver != 'GTiff':
        raise HTTPException(422, 'Se requiere un GeoTIFF, no otro formato raster.')
    if src.crs is None:
        raise HTTPException(422, 'El raster no tiene CRS.')
    dtype = np.dtype(src.dtypes[0])
    if src.count != 1 or dtype.kind not in 'iuf' or dtype.itemsize < 2:
        raise HTTPException(422, 'Se requiere un DEM de una banda numérica de más de 8 bits, no una imagen RGB.')
    if src.width < 2 or src.height < 2:
        raise HTTPException(422, 'El DEM debe tener al menos 2 × 2 píxeles.')
    if not all(math.isfinite(x) for x in src.transform) or src.transform.determinant == 0:
        raise HTTPException(422, 'La transformación espacial del DEM no es válida.')
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
    if not all(math.isfinite(x) for x in b) or b[0] >= b[2] or b[1] >= b[3] or b[0] < -180 or b[2] > 180 or b[1] < -90 or b[3] > 90:
        raise HTTPException(422, 'Cobertura inválida o cruce del antimeridiano no soportado.')
    return b


@lru_cache(maxsize=8)
def _inspeccionar_dem(path, size, mtime_ns, ctime_ns):
    """Scan physical heights once per file revision, in bounded memory.

    Reject undeclared sentinels before interpolation can contaminate neighbors.
    Explicit NoData and raster masks are excluded from the scan.
    """
    with rasterio.open(path) as src:
        validar_raster(src)
        bounds_marcianos(src)
        minimum, maximum, count = math.inf, -math.inf, 0
        for row in range(0, src.height, 256):
            values = src.read(1, window=rasterio.windows.Window(
                0, row, src.width, min(256, src.height-row)), masked=True).compressed()
            if not values.size:
                continue
            if not np.isfinite(values).all() or np.any(values < -15000) or np.any(values > 30000):
                raise HTTPException(422, 'Alturas no físicas o NoData sin declarar; corrige la máscara antes de interpolar.')
            minimum = min(minimum, float(values.min()))
            maximum = max(maximum, float(values.max()))
            count += values.size
        if not count:
            raise HTTPException(422, 'El DEM no contiene alturas válidas.')
        return {'min_m': minimum, 'max_m': maximum, 'valid_cells': int(count),
                'nodata_cells': int(src.width*src.height-count)}


def resolucion_superficie(src, bbox):
    """Approximate native pixel spacing on the Mars sphere at the crop center."""
    from pyproj import Geod
    x, y = transform_coords(MARS_LONLAT_CRS, src.crs,
                           [(bbox[0]+bbox[2])/2], [(bbox[1]+bbox[3])/2])
    a = src.transform
    lon, lat = transform_coords(src.crs, MARS_LONLAT_CRS,
                               [x[0], x[0]+a.a, x[0]+a.b],
                               [y[0], y[0]+a.d, y[0]+a.e])
    geod = Geod(a=MARS_RADIUS_M, b=MARS_RADIUS_M)
    return [abs(geod.inv(lon[0], lat[0], lon[i], lat[i])[2]) for i in (1, 2)]


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
    path = BASE_DIR / HTML_NAME
    if not path.is_file():
        path = BASE_DIR / 'index.html'
    if not path.is_file():
        raise HTTPException(404, f'Coloca {HTML_NAME} o index.html junto al servidor.')
    return FileResponse(path, media_type='text/html')


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
    path = None
    try:
        path = encontrar_tif()
        data = obtener_dem(min_lon=None, min_lat=None, max_lon=None, max_lat=None, size=40)
        return {'status': 'activo', 'tif_detectado': path.name,
                'dem_validated': True, 'provenance_verified': data['provenance']['verified'],
                'provenance': data['provenance'], 'full_bbox': data['full_bbox'],
                'source_resolution_m': data['source_resolution_m'],
                'crs': data['source_crs'], 'source_width': data['source_width'],
                'source_height': data['source_height'], 'source_resolution': data['source_resolution'],
                'science_status': 'DEM georreferenciado validado; no certifica seguridad EVA',
                'source_elevation_stats': data['source_elevation_stats'],
                'detail': 'GeoTIFF marciano validado; se procesó una malla de comprobación.'}
    except HTTPException as exc:
        return {'status': 'sin_dem' if exc.status_code == 404 else 'dem_invalido',
                'tif_detectado': path.name if path else None,
                'dem_validated': False, 'provenance_verified': False, 'detail': exc.detail}


@app.get('/api/dem/jezero')
def obtener_dem(
    min_lon: Annotated[Optional[float], Query(ge=-180, le=180)] = None,
    min_lat: Annotated[Optional[float], Query(ge=-90, le=90)] = None,
    max_lon: Annotated[Optional[float], Query(ge=-180, le=180)] = None,
    max_lat: Annotated[Optional[float], Query(ge=-90, le=90)] = None,
    size: Annotated[int, Query(ge=40, le=440)] = 110,
):
    # The preparation CLI calls this function directly, bypassing FastAPI Query validation.
    if not isinstance(size, int) or isinstance(size, bool) or not 40 <= size <= 440:
        raise HTTPException(422, 'size debe ser un entero entre 40 y 440.')
    requested = (min_lon, min_lat, max_lon, max_lat)
    if any(v is not None for v in requested):
        if not all(v is not None and math.isfinite(v) for v in requested):
            raise HTTPException(422, 'Envía los cuatro límites finitos del recorte.')
        if min_lon >= max_lon or min_lat >= max_lat:
            raise HTTPException(422, 'Los mínimos deben ser menores que los máximos.')
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise HTTPException(422, 'Coordenadas fuera del rango de longitud/latitud.')
    path = encontrar_tif()
    try:
        stats = _inspeccionar_dem(*_file_key(path))
        provenance = procedencia_dem(path)
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
            source_resolution_m = [value * src.crs.linear_units_factor[1] for value in src.res] if src.crs.is_projected else None
            source_ground_resolution_m = resolucion_superficie(src, bbox)
            # Resolution is sampling spacing, not a guarantee of obstacle detection.
            sampling_ratios = [cell_x/source_ground_resolution_m[0], cell_y/source_ground_resolution_m[1]]
            downsample = max(sampling_ratios)
            requested_covered = min_lon is None or all(
                abs(a-b) < 1e-10 for a, b in zip(requested, bbox))
            return {
                'source_file': path.name, 'source_crs': src.crs.to_string(),
                'provenance': provenance, 'source_elevation_stats': stats,
                # Compatibility with the existing static science-release builder.
                'source_url': provenance.get('source_url'),
                'download_url': provenance.get('retrieved_url'),
                'source_sha256': provenance.get('sha256'),
                'source_institution': 'USGS Astrogeology Science Center' if provenance['verified'] else 'Not independently verified; inspect this input GeoTIFF.',
                'scientific_limitations': 'Measured surface heights resampled to a DEM grid; not rover-verified walking safety, real-time weather, or subcell obstacle detection.',
                'crs': MARS_LONLAT_CRS, 'coordinate_order': 'longitude, latitude',
                'elevation_units': 'm', 'units_assumed': not bool(src.units[0]),
                'pixel_registration': 'area', 'resampling': 'bilinear', 'row_order': 'north_to_south',
                'grid_origin': 'upper_left', 'nodata_representation': 'null',
                'grid_transform': list(transform)[:6],
                'source_width': src.width, 'source_height': src.height,
                'source_resolution': list(src.res),
                'source_resolution_m': source_resolution_m,
                'source_resolution_m_approx': source_ground_resolution_m,
                'downsampling_factor_approx': downsample,
                'sampling_ratio_xy': sampling_ratios,
                'upsampled': any(ratio < 1 for ratio in sampling_ratios),
                'resolution_note': 'La malla puede omitir obstáculos subcelda; interpolar no añade detalle.',
                'requested_bbox': list(requested) if min_lon is not None else None,
                'requested_bbox_fully_covered': requested_covered,
                'width': size, 'height': size, 'bbox': bbox, 'full_bbox': full,
                'cell_size_m': (cell_x+cell_y)/2, 'cell_size_x_m': cell_x, 'cell_size_y_m': cell_y,
                'valid_fraction': float(valid.mean()), 'nodata_cells': int((~valid).sum()),
                'elevation_min_m': float(dst[valid].min()), 'elevation_max_m': float(dst[valid].max()),
                'elevations': [float(v) if np.isfinite(v) else None for v in dst.ravel()],
            }
    except HTTPException:
        raise
    except (rasterio.errors.RasterioError, ValueError, OSError) as exc:
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
