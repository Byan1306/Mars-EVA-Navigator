# Mars Jezero HiRISE Surface — módulo independiente

**Objetivo:** producir un sector auténtico de superficie marciana que después
se integrará en Mars EVA Navigator, sin tocar todavía el astronauta, los
controles ni las rutas EVA.

## Qué es realmente medido y qué no

- **Sí, medido:** elevaciones del mosaico DTM HiRISE TRN 2020, USGS, 1 m por
  muestra en su proyección; se exportan como mallas GLB triangulares y una
  rejilla binaria de alturas absolutas. La elevación geométrica es 1:1, sin
  ruido ni relieves añadidos.
- **Sí, observado:** ortofoto HiRISE USGS de ~0,25 m por píxel, si es accesible
  y tiene >95 % cobertura válida del sector. Se publica en escala de grises y
  se registra a la superficie. **Resolución de foto ≠ precisión del relieve**.
- **No medido:** cielo, iluminación, ajuste cromático, velocidad de caminar
  y cualquier modelo de astronauta que otro desarrollador incorpore.
- **No incluido:** piedras individuales verificadas mediante datos estéreo
  rover; zonas exteriores a la cobertura científica; un mundo 3D infinito.

## Fuentes oficiales y resolución

- [USGS HiRISE DTM Jezero](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_dtm_mosaic)
  — DOI [10.5066/P9REJ9JN](https://doi.org/10.5066/P9REJ9JN), ~1 m
  por muestra, fichero fuente ~1,8 GB.
- [USGS HiRISE ortho Jezero](https://astrogeology.usgs.gov/search/map/mars_2020_terrain_relative_navigation_hirise_orthorectified_image_mosaic)
  — DOI [10.5066/P9QJDP48](https://doi.org/10.5066/P9QJDP48), ~0,25 m
  por píxel, fichero fuente ~6,9 GB.
- Datos publicados por USGS Astrogeology a partir de HiRISE/MRO.
  Ver URLs exactas en `terrain_manifest.json`.

El pipeline lee recortes espaciales del GeoTIFF oficial por HTTP Range usando
GDAL. **No declara el SHA-256 del original completo sin descargarlo**; sí
registra el SHA-256 de cada malla, textura y fichero derivado exportado.

## Salida del constructor

```text
Mars_Jezero_Real_Surface/
  terrain_manifest.json
  terrain_loader.mjs
  preview.html
  README.md
  assets/
    height_1m.f32        # alturas absolutas m, float32 little endian
    mask_1m.bin          # uint8; 1=muestra válida, 0=NoData
    tiles/
      r0_c0_lod1.glb
      r0_c0_lod2.glb
      r0_c0_lod4.glb
      r0_c0_lod8.glb
      ...                # 16 tiles de 256m si se procesan 1024m
    textures/
      r0_c0_hirise_25cm.png
      ...                # imágenes si las fuentes oficiales están disponibles
    masks/
      r0_c0.png
      ...
  vendor/                # módulo Three.js copiado para vista previa offline
  reports/
    validation.json
```

## Generación

Es necesario Python >=3.12 con Rasterio, NumPy, PyProj y Pillow, además de
acceso a los datos USGS. Se puede ejecutar desde el repositorio:

```bash
python -m pip install -r requirements.txt
npm install --no-audit --no-fund
python surface_hirise/prepare_surface.py --output _hires_surface/Mars_Jezero_Real_Surface --tiles 4
```

`--tiles 1` construye 256m × 256m para un test más rápido y
`--no-ortho` omite la imagen; en ese caso no se pretende que exista una
textura HiRISE. Los valores son parámetros del constructor, no resoluciones
inventadas.

### Vista previa

Copia el módulo Three.js y sus dos archivos de apoyo al subdirectorio
`vendor/` del resultado (el workflow de GitHub lo hace automáticamente).
Desde su carpeta principal, ejecuta:

```bash
python -m http.server 8765
```

Abre `http://127.0.0.1:8765/preview.html`.

## Integración futura con el explorador

Se importa `createMeasuredJezeroSurface({scene, manifestUrl, initialLOD})`.
El resultado proporciona:

- `group`: grupo Three.js con mallas genuinas y escala Y 1:1.
- `sampleHeight(x,z)`: altura **relativa a la referencia del sector** en
  metros, o `null` fuera de los datos.
- `sampleAbsolute(x,z)`: altura DTM absoluta original, o `null`.
- `sampleSlopeDegrees(x,z)`: pendiente aproximada derivada del DTM, no
  una garantía de seguridad para EVA.
- `setLOD(1|2|4|8)`: cambia todos los tiles simultáneamente para evitar
  grietas por mezcla de distintos niveles.
- `setAppearance({tint:true|false})`: colorización artística separable.
- `dispose()`: libera buffers y texturas GPU.

El sistema del módulo es X este, Y altura relativa al centro y Z sur,
centrado en el producto HiRISE. La transformación al sistema actual de Mars
EVA Navigator **debe considerar la referencia vertical y el origen del DEM**
y no debe mezclarse sin verificar la correspondencia entre ambos.

### Límites

1. La proyección equirectangular marciana tiene ligera diferencia entre
   distancia este-oeste proyectada y distancia local física; el exportador
   utiliza cos(latitud central) para el eje X e informa el factor.
2. NoData produce huecos sin mallas, incluso al bajar el nivel de detalle.
3. LOD 2/4/8 no añade datos, solo simplifica los 1m originales.
4. Las imágenes HiRISE son escala de grises; una colorización cálida es una
   elección visual, no color verdadero observado desde Marte.
5. La luz y el horizonte mostrado en `preview.html` son ilustrativos.
6. Para conectar con CTX regional y MOLA se requiere una fase de
   georregistro, transiciones verticales validadas y streaming multirresolución.
7. La cobertura real y el estado de descarga se obtienen del manifiesto
   generado. **Si faltan datos, el proceso falla o declara que faltan**.

Ni el modelo de astronauta ni la aplicación principal se modifican en esta
entrega.
