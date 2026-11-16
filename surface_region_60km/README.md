# Mars EVA Navigator — Jezero 60 × 60 km · mapa geológico con nombres

## Mapa de 60 kilómetros auténticos

Se utiliza el **Mars 2020 Science Investigation CTX DEM Mosaic** de USGS (2021),
que cubre todo Jezero y sus alrededores. La superficie tiene 60 km de anchura,
60 km de longitud y muestras de altura derivadas del DTM orbital CTX de 20 m.
Esta extensión **NO** equivale a 60 km con detalle HiRISE de 1 m; el parche
HiRISE ya generado sigue siendo un producto independiente de 1 × 1 km.

El renderizador permite vuelo y caminata virtual, carga geometría por tiles,
muestra un minimapa y permite seleccionar sitios con nombre. **No garantiza
que las rutas sean seguras para EVA**: la topografía no detecta rocas pequeñas.

## Fuentes USGS/NASA

- DTM regional de 20 m: [Mars 2020 Science Investigation CTX DEM Mosaic](https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic). Publicado 2021; mosaico de USGS basado en CTX MRO y el Ames Stereo Pipeline.
- Fotografía ortorrectificada de 5 m: [mosaico CTX complementario](https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/CTX/index.html), archivo `ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXortho_mosaic_5m.tif`.
- [Nomenclátor oficial IAU/USGS](https://planetarynames.wr.usgs.gov/) para Jezero, Belva, Neretva Vallis, Sava Vallis, Pliva Vallis y el límite de Jezero Mons.
- Lugar de aterrizaje Octavia E. Butler: Farley et al. 2022, *Science*, coordenadas publicadas 18.4447° N, 77.4508° E.
- Sitios de misión Three Forks, Séítah y frente del delta: **marcadores de referencia aproximados** derivados de posiciones/visitas publicadas, no centroides topográficos oficiales. El manifiesto distingue su grado de precisión y proporciona sus fuentes.

### Lugares que aparecerán

| Nombre | Clase | Precisión de marcador |
|---|---|---|
| Cráter Jezero | Cráter | Centro oficial IAU/USGS |
| Cráter Belva | Cráter | Centro oficial IAU/USGS |
| Neretva Vallis | Valle | Centro oficial IAU/USGS |
| Sava Vallis · sector sur | Valle | Punto de su geometría oficial, **no su centro** |
| Pliva Vallis · entrada | Valle | Punto de su geometría oficial, **no su centro** |
| Jezero Mons · borde | Monte | Punto de la geometría oficial, **no su cima** |
| Octavia E. Butler | Zona de aterrizaje | Posición publicada de la misión |
| Three Forks | Zona de muestras | Referencia aproximada |
| Séítah | Unidad geológica | Referencia aproximada |
| Frente del delta | Unidad geológica | Referencia aproximada |

Si un marcador está fuera del terreno medido o sobre una celda NoData,
no se autoriza su teletransporte.

## Ejecutar

Descomprime el ZIP y ejecuta `INICIAR_JEZERO_60KM.bat` en Windows (Python 3),
o inicia `python -m http.server 8765` dentro de la carpeta y abre
`http://127.0.0.1:8765/region.html`.

- **WASD:** moverse.
- **Ratón:** mirar alrededor tras hacer clic en el visor.
- **Shift:** acelerar.
- **F:** alternar caminar/vuelo.
- **Espacio/C:** ascender/descender en modo vuelo.
- **ESC:** liberar ratón.
- **Minimapa o listado:** visitar lugares documentados.

## Arquitectura

- `terrain_manifest.json`: procedencia, extensión, resolución, NoData,
  SHA-256 de originales procesados y de derivados, coordenadas de 10 lugares,
  precisión, cobertura, y listado de tiles de imagen.
- `assets/height_ctx_20m.f32`: grid 3001×3001 float32 de **elevación absoluta
  USGS** en m; orden de filas norte→sur.
- `assets/mask_ctx.bin`: máscara 0/1 para evitar representar zonas sin datos.
- `assets/textures/*.jpg`: recortes de la ortofoto oficial de 5 m,
  reescalados a 1024 px por tile (~4,9 m/píxel), solo si el raster fuente
  pasó los filtros de CRS/cobertura.
- `region_world.mjs`: Three.js, carga por proximidad, LOD adaptativo y
  nombres 3D + lista/minimapa. **No inventa elevaciones**.
- `validation.json`: resultados de integridad geométrica y procedencia.

## Exactitud y límites

- La **geometría** se deriva del DEM oficial; usa interpolación bilineal al
  remuestrear al grid de visualización (no aporta detalle nuevo).
- El radio usado es el especificado en el CRS del archivo original; **no se
  presupone** que coincide con el del HiRISE antiguo (3.396.190 m).
- La extensión se mide en coordenadas locales, compensando el factor
  cos(latitud) para la distancia este-oeste sobre Marte.
- La escala vertical es 1:1 y NoData no se rellena.
- Las imágenes en escala de grises son observaciones orbitales; el
  contraste, tono cálido, cielo y luces son **apariencia ilustrativa**.
- La malla cercana/futura HiRISE (1 m) requiere georregistro y una revisión
  del sistema de alturas antes de mezclar físicamente las dos superficies.
- Las coordenadas de nombres oficiales son centros o puntos geométricos
  representativos y **no implican** que el rover haya visitado esos lugares.
- La carga de tiles aún no tiene un índice espacial optimizado ni un modelo
  certificado de caminata EVA; es un prototipo de exploración y visualización.

## Reconstrucción reproducible

```bash
python -m pip install -r requirements.txt
npm install
python surface_region_60km/prepare_region.py --output _region60km/Jezero_60km
python surface_region_60km/verify_region.py _region60km/Jezero_60km
python surface_region_60km/build_region.py _region60km/Jezero_60km
```

Si la ortofoto remota no puede descargarse, se puede generar el
**terreno auténtico sin fotografía** con `--no-photo`; jamás se
sustituyen datos faltantes por otros inventados.
