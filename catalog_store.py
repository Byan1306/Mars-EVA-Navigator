"""Local evidence catalog. Validation preserves supplied provenance, not scientific certification."""
import json
import math
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

CRS = 'Mars_2015_sphere_3396190_planetocentric_east'
MISSIONS = {'Perseverance': 'Jezero', 'Curiosity': 'Gale'}

def official_url(value):
    parsed = urlparse(value or '')
    host = parsed.hostname or ''
    return parsed.scheme == 'https' and (host == 'nasa.gov' or host.endswith('.nasa.gov') or host in ('an.rsl.wustl.edu', 'pds-geosciences.wustl.edu'))

def validate_record(record):
    if not isinstance(record, dict):
        raise ValueError('Cada registro debe ser un objeto')
    for key in ('id', 'mission', 'region', 'kind', 'title', 'source', 'category'):
        if not isinstance(record.get(key), str) or not record[key]:
            raise ValueError(f'Falta {key}')
    if MISSIONS.get(record['mission']) != record['region']:
        raise ValueError('Misión y región incompatibles')
    if record['kind'] not in ('photo', 'station', 'objective') or record['category'] not in ('A','B','C'):
        raise ValueError('Tipo o categoría inválida')
    if not official_url(record['source']):
        raise ValueError('Se requiere ficha oficial NASA/PDS')
    if record['category'] == 'A':
        position = record.get('position')
        if not isinstance(position, list) or len(position) != 2 or not all(type(v) in (int,float) and math.isfinite(v) for v in position):
            raise ValueError('Posición A inválida [lat, lon]')
        lat, lon = position
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Coordenadas fuera de intervalo')
        if record.get('crs') != CRS or not official_url(record.get('position_source')):
            raise ValueError('Falta convención de coordenadas o evidencia de localización')
        if record.get('location_role') != ('camera' if record['kind']=='photo' else 'site'):
            raise ValueError('Se requiere posición de cámara/sitio explícita')
        if type(record.get('uncertainty_m')) not in (float,int) or record['uncertainty_m'] < 0 or not math.isfinite(record['uncertainty_m']):
            raise ValueError('Falta incertidumbre de localización')
    elif record.get('position') is not None:
        raise ValueError('B/C no deben contener una posición precisa')
    if record['kind']=='station' and (record['category']!='A' or type(record.get('sol')) is not int or record['sol']<0):
        raise ValueError('Estación requiere categoría A y sol documentado')
    if record['kind']=='photo':
        for field in ('image_url','thumbnail_url'):
            url=record.get(field)
            if url and urlparse(url).scheme!='https':raise ValueError('Imagen requiere HTTPS')
    return record

class Catalog:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, mission TEXT, kind TEXT, category TEXT, lat REAL, lon REAL, body TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS location ON records(mission,kind,category,lat,lon)')
    def connect(self):
        return sqlite3.connect(self.path)
    def replace(self, records):
        checked=[validate_record(dict(r)) for r in records]
        if len({r['id'] for r in checked})!=len(checked):raise ValueError('Identificadores duplicados')
        with self.connect() as db:
            db.execute('DELETE FROM records')
            for r in checked:
                lat,lon=r.get('position') or (None,None)
                db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?)',(r['id'],r['mission'],r['kind'],r['category'],lat,lon,json.dumps(r,ensure_ascii=False)))
    def list(self, mission=None, kind=None):
        query='SELECT body FROM records WHERE 1=1';params=[]
        for column,value in [('mission',mission),('kind',kind)]:
            if value:query+=f' AND {column}=?';params.append(value)
        with self.connect() as db:return [json.loads(row[0]) for row in db.execute(query,params)]
    def nearby(self, mission, lat, lon, radius):
        span=math.degrees(radius/3396190)
        with self.connect() as db:
            candidates=[json.loads(row[0]) for row in db.execute("SELECT body FROM records WHERE mission=? AND kind='photo' AND category='A' AND lat BETWEEN ? AND ?",(mission,lat-span,lat+span))]
        result=[]
        for r in candidates:
            a,b=r['position'];dlat=math.radians(a-lat);dlon=math.radians(b-lon)
            h=math.sin(dlat/2)**2+math.cos(math.radians(lat))*math.cos(math.radians(a))*math.sin(dlon/2)**2
            distance=2*3396190*math.asin(math.sqrt(min(1,max(0,h))))
            if distance<=radius:result.append({**r,'distance_m':distance})
        return sorted(result,key=lambda r:r['distance_m'])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Validate and atomically replace local catalog from JSON list')
    parser.add_argument('file');parser.add_argument('--database',default=str(Path(__file__).with_name('catalog.sqlite')))
    args=parser.parse_args()
    Catalog(args.database).replace(json.loads(Path(args.file).read_text(encoding='utf-8')))
    print('Catálogo validado e importado. La evidencia de localización requiere revisión científica humana.')
