/*
 * Curiosity Mission Explorer — NASA/JPL-Caltech geometry via CC BY 4.0
 * azmth.space compilation. Panoramas link directly to NASA source records.
 * This module NEVER invents rover positions or labels interpolated sols exact.
 */
(function (root) {
  'use strict';
  const FULL_SOURCE = 'https://azmth.space/data/mars-traverses/curiosity.json';
  const OFFICIAL_WAYPOINTS = 'https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json';
  const NASA_LOCATION = 'https://science.nasa.gov/mission/msl-curiosity/location-map/';
  const MARS_RADIUS_M = 3396190;
  const BASE_TILES = 'https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg';
  const NASA_TILES = Object.freeze({
    hirise: 'https://trek.nasa.gov/tiles/Mars/EQ/curiosity_hirise_mosaic/1.0.0/default/default028mm/{z}/{y}/{x}.png',
    ctx: 'https://trek.nasa.gov/tiles/Mars/EQ/Gale_CTX_BlockAdj_dd/1.0.0/default/default028mm/{z}/{y}/{x}.png'
  });
  const HI_BOUNDS = [[-4.9254743,137.1224669],[-4.2489588,137.7298129]];
  const CTX_BOUNDS = [[-6.5732988,135.1842593],[-2.8077809,139.2413012]];
  // Missing high-resolution coverage is transparent; regional CTX and Viking stay
  // underneath. Do not imply that a tile enlarged past its native level adds detail.
  const NASA_PHOTO_API = 'https://mars.nasa.gov/api/v1/raw_image_items/';
  const CAMERAS = new Set(['all','NAV_LEFT_A','NAV_RIGHT_A','MAST_LEFT','MAST_RIGHT','MAHLI','FHAZ_LEFT_A']);


  // All source pages explicitly describe 360-degree panoramas (cylindrical horizontal
  // mosaics or Mastcam panoramic sweeps). Coordinates are NOT asserted by these pages.
  // The map anchors each image to its contemporaneous, published rover path/sol.
  const PANORAMAS = Object.freeze([
    { id:'rocknest', sol:59, endSol:60, name:'Rocknest · primeras muestras',
      camera:'Navcam · panorámica cilíndrica', year:2012,
      source:'https://science.nasa.gov/resource/curiositys-location-during-first-scooping/',
      image:'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/mars/downloadable_items/3/6/36478_pia16227_Navcam_sols59-60-cyl.jpg?fit=clip&w=5000',
      note:'Panorama auténtico Navcam de los sols 59–60; montaje cilíndrico horizontal.' },
    { id:'verarubin', sol:1996, name:'Vera Rubin Ridge · Navcam 360°',
      camera:'Navcam derecha · proyección cilíndrica', year:2018,
      source:'https://science.nasa.gov/resource/sol-1996-right-navigation-camera-cylindrical-perspective/',
      image:'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/mars/resources/deepzooms/2/24404_N_R000_1996_ILT068CYPTSB2396_DRIVEM1.png?fit=clip&w=6000',
      note:'Panorámica estereoscópica derecha de Sol 1996; la imagen NASA debe abrirse desde su ficha.' },
    { id:'rockhall', sol:2265, name:'Rock Hall · cresta Vera Rubin',
      camera:'Mastcam izquierda · mosaico 360°', year:2018,
      source:'https://science.nasa.gov/resource/curiositys-360-panorama-of-rock-hall/',
      image:'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/mars/downloadable_items/4/42462_PIA23042.jpg?fit=clip&w=6000',
      note:'Panorama Mastcam de 122 fotografías tomado el sol 2265. Puede requerir abrir el original de gran tamaño.' },
    { id:'sol3511', sol:3511, name:'Monte Sharp · Navcam 360°',
      camera:'Navcam derecha · proyección cilíndrica', year:2022,
      source:'https://science.nasa.gov/resource/sol-3511-right-navigation-camera-cylindrical-projection/',
      image:'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/mars/resources/deepzooms/2/6/26827_N_R000_3511XEDR095CYLASB3152_AUTOLM1.png?fit=clip&w=6000',
      note:'Panorámica de los sols 3509–3511, ensamblada a partir de imágenes Navcam.' },
    { id:'sol3962', sol:3962, name:'Laderas de Gale · 2023',
      camera:'Navcam derecha · proyección cilíndrica', year:2023,
      source:'https://science.nasa.gov/resource/sol-3962-right-navigation-camera-cylindrical-projection/',
      image:'https://assets.science.nasa.gov/dynamicimage/assets/science/psd/mars/resources/deepzooms/2/7/27720_N_R000_3962XEDR105CYLASB0106_AUTOLM1.png?crop=faces%2Cfocalpoint&fit=clip&h=2232&w=7665',
      note:'Panorámica NASA Navcam registrada entre los sols 3960 y 3962.' },
    { id:'sol4294', sol:4294, name:'Canal Gediz Vallis · 2024',
      camera:'Navcam derecha · proyección cilíndrica', year:2024,
      source:'https://science.nasa.gov/resource/sol-4294-right-navigation-camera-cylindrical-projection/',
      image:'https://science.nasa.gov/wp-content/uploads/2024/09/sol-4294-right-navigation-camera-cylindrical-projection.jpg',
      note:'Panorámica NASA Navcam correspondiente al sol 4294.' },
    { id:'sol4323', sol:4323, name:'Monte Sharp · 2024',
      camera:'Navcam derecha · proyección cilíndrica', year:2024,
      source:'https://science.nasa.gov/resource/sol-4323-right-navigation-camera-cylindrical-projection/',
      image:'https://science.nasa.gov/wp-content/uploads/2024/10/n-r000-4323-edr109cylasb1290-autolm1.png',
      note:'Panorámica de sol 4323; acceder a la ficha NASA para descargar la imagen.' },
    { id:'boxwork', sol:4451, endSol:4454, name:'Boxwork · primera panorámica',
      camera:'Mastcam · 291 imágenes', year:2025,
      source:'https://science.nasa.gov/photojournal/curiositys-first-360-degree-view-of-boxwork-patterns/',
      image:'https://photojournal.jpl.nasa.gov/jpegMod/PIA26559_modest.jpg',
      note:'Primera panorámica 360° documentada del relieve boxwork (sols 4451–4454).' },
    { id:'sajama', sol:4714, endSol:4741, name:'Nevado Sajama · 1,5 gigapíxeles',
      camera:'Mastcam · 1031 imágenes', year:2025,
      source:'https://science.nasa.gov/photojournal/curiosity-captures-a-360-degree-view-at-nevado-sajama/',
      image:null,
      note:'Mosaico 360° capturado durante los sols 4714–4741; original de muy alta resolución, disponible en NASA. No se descarga automáticamente.' },
    { id:'sol4834', sol:4834, name:'Boxwork · Navcam 2026',
      camera:'Navcam derecha · proyección cilíndrica', year:2026,
      source:'https://science.nasa.gov/resource/sol-4834-right-navigation-camera-cylindrical-projection/',
      image:'https://assets.science.nasa.gov/dynamicimage/assets/science/missions/msl/2026/mosaics/march/N_R000_4834_EDR121CYLASB0000_AUTOLM1.jpg?fit=clip&w=6000',
      note:'NASA documentó un mosaico 360° en el sol 4834, el 13 de marzo de 2026.' }
  ]);

  function finite(value) {
    return typeof value === 'number' && Number.isFinite(value);
  }
  function normalizedLon(lon) {
    return lon > 180 ? lon - 360 : lon;
  }
  function marsDistanceMeters(a, b) {
    const lat1 = a[0] * Math.PI / 180;
    const lat2 = b[0] * Math.PI / 180;
    const dlat = lat2 - lat1;
    const dlon = (b[1] - a[1]) * Math.PI / 180;
    const sin2 = Math.sin(dlat / 2) ** 2 +
      Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
    return 2 * MARS_RADIUS_M * Math.atan2(Math.sqrt(Math.max(0, sin2)), Math.sqrt(Math.max(0, 1 - sin2)));
  }
  function parseTraverse(input) {
    if (!input || input.slug !== 'curiosity' || !input.path) throw Error('La fuente no contiene el recorrido Curiosity.');
    const path = input.path;
    if (!Array.isArray(path.lon) || !Array.isArray(path.lat) || !Array.isArray(path.sol) ||
        path.lon.length < 100 || path.lon.length > 200000 ||
        path.lon.length !== path.lat.length || path.lon.length !== path.sol.length) {
      throw Error('El recorrido no contiene columnas de coordenadas y sols coherentes.');
    }
    const coords = [];
    const sols = [];
    let geometryM = 0;
    for (let i = 0; i < path.lon.length; i++) {
      const lat = path.lat[i], lon = normalizedLon(path.lon[i]), sol = path.sol[i];
      if (![lat, lon, sol].every(finite) ||
          lat < -90 || lat > 90 || lon < -180 || lon > 180 ||
          (i && sol < sols[i - 1])) {
        throw Error('Una posición o su sol no supera la validación.');
      }
      const point = [lat, lon];
      if (i) geometryM += marsDistanceMeters(coords[i - 1], point);
      coords.push(point);
      sols.push(sol);
    }
    // Distinguish geometric length of the mapped line from NASA wheel odometry.
    return {
      coords: coords, sols: sols, geometryM: geometryM,
      sourceKind: 'full', fetched: typeof input.fetched === 'string' ? input.fetched : 'sin fecha',
      attribution: 'NASA/JPL-Caltech; compilación azmth.space (CC BY 4.0).',
      notes: 'Sols exactos solo en waypoints NASA; intermedios interpolados por el compilador.'
    };
  }
  function parseOfficialWaypoints(input) {
    if (!input || !Array.isArray(input.features)) throw Error('La fuente NASA de waypoints no tiene GeoJSON.');
    const positions = [];
    for (const feat of input.features) {
      const ll = feat && feat.geometry && feat.geometry.coordinates;
      const prop = feat && feat.properties || {};
      const rawSol = prop.sol ?? prop.SOL ?? prop.sol_number;
      const sol = Number(rawSol);
      if (!Array.isArray(ll) || !finite(ll[0]) || !finite(ll[1]) ||
          !Number.isFinite(sol) || sol < 0 || Math.abs(ll[1]) > 90) continue;
      const lon = normalizedLon(ll[0]);
      if (lon < -180 || lon > 180) continue;
      positions.push({ sol: sol, coords: [ll[1], lon] });
    }
    positions.sort((a, b) => a.sol - b.sol);
    if (positions.length < 20) throw Error('No hay suficientes waypoints válidos de NASA.');
    let geometryM = 0;
    for (let i = 1; i < positions.length; i++) geometryM += marsDistanceMeters(positions[i-1].coords, positions[i].coords);
    return {
      coords: positions.map(p => p.coords), sols: positions.map(p => p.sol),
      geometryM: geometryM, sourceKind: 'waypoints', fetched: 'no informada',
      attribution: 'NASA/JPL-Caltech, MMGIS MSL waypoints.',
      notes: 'SOLO paradas de conducción: segmentos rectos aproximados entre waypoints; NO es el trazado exacto de las ruedas.'
    };
  }
  function nearestIndex(sols, targetSol) {
    let lo = 0, hi = sols.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1;
      if (sols[mid] < targetSol) lo = mid + 1;
      else hi = mid;
    }
    if (lo > 0 && Math.abs(sols[lo - 1] - targetSol) < Math.abs(sols[lo] - targetSol)) return lo - 1;
    return lo;
  }

  function validatedNASAUrl(url) {
    if (typeof url !== 'string' || !url) return null;
    try {
      const parsed = new URL(url, 'https://mars.nasa.gov/');
      return parsed.protocol === 'https:' &&
        (parsed.hostname === 'nasa.gov' || parsed.hostname.endsWith('.nasa.gov')) ? parsed.href : null;
    } catch (_) { return null; }
  }
  function curiosityPhotosURL(sol, camera='all', page=0) {
    if (!Number.isInteger(sol) || sol < 0 || sol > 10000 ||
        !CAMERAS.has(camera) || !Number.isInteger(page) || page < 0 || page > 999) {
      throw Error('Sol, cámara o página fuera del intervalo permitido.');
    }
    const params=new URLSearchParams({
      'condition_1':'msl:mission',
      'condition_2':sol+':sol:gte',
      'condition_3':sol+':sol:lte',
      'per_page':'24', 'page':String(page),
      'order':'sol desc',
      'extended':'thumbnail::sample_type::noteq'
    });
    if(camera!=='all')params.set('search','|'+camera);
    return NASA_PHOTO_API+'?'+params.toString();
  }
  function normalizeRawPhotos(payload) {
    const raw = Array.isArray(payload) ? payload :
      [payload?.items,payload?.images,payload?.data,payload?.results,payload?.raw_image_items].find(Array.isArray) || [];
    const unique=new Set();
    const output=[];
    for(const image of raw) {
      if(!image || typeof image!=='object')continue;
      const files=image.image_files || image.files || {};
      const direct = image.img_src || image.image_url || image.image_src ||
        image.url || image.image || (typeof files==='object' && (files.large || files.medium || files.full || files.small));
      const href=validatedNASAUrl(typeof direct==='string'?direct:direct?.url);
      if(!href || unique.has(href))continue;
      unique.add(href);
      const sol=Number(image.sol ?? image.sol_number ?? image.martian_sol);
      const cam=image.instrument || image.camera || image.instrument_name || image.camera_name || 'Cámara NASA';
      output.push({
        url:href, sol:Number.isFinite(sol)?sol:null,
        camera:typeof cam==='string'?cam:(cam?.name||cam?.instrument||'Cámara NASA'),
        title:String(image.title||image.imageid||image.image_id||'Fotografía original Curiosity').slice(0,110)
      });
    }
    const total=Number(payload?.total_results ?? payload?.total ?? payload?.count);
    return {photos:output,total:Number.isFinite(total)?total:null};
  }

  root.CuriosityData = { parseTraverse, parseOfficialWaypoints, nearestIndex, marsDistanceMeters, PANORAMAS, curiosityPhotosURL, normalizeRawPhotos, validatedNASAUrl };

  if (typeof document === 'undefined') return;

  const state = { map:null, track:null, allLine:null, progressLine:null, roverMarker:null,
    panoMarkers:[], selectedSol:0, activePano:null, panRatio:0.5, dragging:false,
    dragStartX:0, dragRatio:0.5, zoom:1, timer:null, loaded:false, loading:false, overlayOpen:false,
    tileLayers:null, mapMode:'hirise', rawPage:0, rawSol:null, rawPhotos:[], rawRequest:0, pano3d:null, importUrl:null };
  function id(name) { return document.getElementById(name); }
  function text(name, value) { const node = id(name); if (node) node.textContent = value; }
  function formatNum(x) { return Number(x).toLocaleString('es-CR', {maximumFractionDigits:1}); }
  function sourceUrlForSol(sol) {
    return 'https://mars.nasa.gov/msl/multimedia/raw-images/?mission=msl&begin_sol=' + Math.floor(sol) + '&end_sol=' + Math.floor(sol);
  }
  function setStatus(value) { text('curiosity-data-status', value); }

  function updateMapMode(mode) {
    if (!state.map || !state.tileLayers || !['hirise','ctx','viking'].includes(mode))return;
    const {global,ctx,hirise}=state.tileLayers;
    if(!state.map.hasLayer(global))global.addTo(state.map);
    if(mode==='viking') {
      if(state.map.hasLayer(hirise))state.map.removeLayer(hirise);
      if(state.map.hasLayer(ctx))state.map.removeLayer(ctx);
    } else if(mode==='ctx') {
      if(state.map.hasLayer(hirise))state.map.removeLayer(hirise);
      if(!state.map.hasLayer(ctx))ctx.addTo(state.map);
    } else {
      if(!state.map.hasLayer(ctx))ctx.addTo(state.map);
      if(!state.map.hasLayer(hirise))hirise.addTo(state.map);
    }
    state.mapMode=mode;
    const captions={
      hirise:'HiRISE sobre CTX. Las zonas fuera de la cobertura de HiRISE se muestran en CTX o Viking. No hay superresolución artificial.',
      ctx:'CTX: cobertura regional del cráter Gale. Zoom excesivo no crea detalle real.',
      viking:'Viking: mosaico global de aproximadamente 232 m/píxel en origen. Se recomienda usar HiRISE o CTX para detalles.'
    };
    text('curiosity-layer-status',captions[mode]);
    for(const key of ['hirise','ctx','viking']){
      const btn=id('curiosity-layer-'+key);
      if(btn){btn.classList.toggle('active',mode===key);btn.setAttribute('aria-pressed',String(mode===key));}
    }
  }

  function createMap() {
    if (state.map) return;
    if (typeof L === 'undefined') { setStatus('No se cargó Leaflet. Conéctate a Internet y recarga.'); return; }
    state.map = L.map('curiosity-map', {
      crs:L.CRS.EPSG4326, preferCanvas:true, zoomControl:true,
      center:[-4.66,137.41], zoom:10, minZoom:1, maxZoom:18, worldCopyJump:false
    });
    const global = L.tileLayer(BASE_TILES, {
      attribution:'NASA/JPL/USGS Mars Trek, Viking MDIM 232 m',
      tileSize:256, maxNativeZoom:7, maxZoom:18, noWrap:true, bounds:[[-90,-180],[90,180]]
    }).addTo(state.map);
    const ctx = L.tileLayer(NASA_TILES.ctx, {
      attribution:'NASA/JPL-Caltech/MSSS/USGS — MRO CTX Gale crater mosaic',
      tileSize:256, minZoom:4, maxNativeZoom:14, maxZoom:18,
      noWrap:true, bounds:CTX_BOUNDS, opacity:1
    }).addTo(state.map);
    const hirise = L.tileLayer(NASA_TILES.hirise, {
      attribution:'NASA/JPL/University of Arizona/USGS — MRO HiRISE Curiosity mosaic',
      tileSize:256, minZoom:7, maxNativeZoom:16, maxZoom:18,
      noWrap:true, bounds:HI_BOUNDS, opacity:1
    }).addTo(state.map);
    state.tileLayers={global,ctx,hirise};
    updateMapMode('hirise');
    let highResTiles=0;
    hirise.on('tileload',function(){highResTiles++;if(highResTiles===1&&state.mapMode==='hirise') text('curiosity-layer-status','HiRISE cargado sobre CTX, con transparencia fuera de su huella. Zoom superior a los datos disponibles no agrega detalle real.');});
    hirise.on('tileerror',function(){if(!highResTiles&&state.mapMode==='hirise')text('curiosity-layer-status','HiRISE no respondió en esta zona o escala; permanece visible el contexto CTX/Viking. Puedes alternar de capa.');});
    state.allLine = L.polyline([], { color:'#6b84a5', weight:3, opacity:.48, smoothFactor:.6, interactive:false }).addTo(state.map);
    state.progressLine = L.polyline([], { color:'#ffae52', weight:4, opacity:.95, smoothFactor:.5, interactive:false }).addTo(state.map);
    state.roverMarker = L.circleMarker([-4.59,137.44], {radius:8,color:'#fff',weight:2,fillColor:'#ff9d37',fillOpacity:1}).addTo(state.map);
    state.roverMarker.bindTooltip('Curiosity · posición en el trazado, sol seleccionado');
    state.map.on('click', function(event) {
      const track = state.track;
      if (!track) return;
      let best = 0, bestDist = Infinity;
      // Clicking the map selects the nearest track vertex. The trail is not a route suggestion.
      for (let i = 0; i < track.coords.length; i++) {
        const a = track.coords[i];
        const dx = (a[1] - event.latlng.lng) * Math.cos(event.latlng.lat * Math.PI / 180);
        const dy = a[0] - event.latlng.lat;
        const d = dx * dx + dy * dy;
        if (d < bestDist) { best = i; bestDist = d; }
      }
      selectSol(track.sols[best], false);
    });
  }
  function drawPanoMarkers() {
    state.panoMarkers.forEach(marker => state.map.removeLayer(marker));
    state.panoMarkers.length = 0;
    if (!state.track) return;
    PANORAMAS.forEach(function(p) {
      if (p.sol < state.track.sols[0] || p.sol > state.track.sols[state.track.sols.length-1]) return;
      const point = state.track.coords[nearestIndex(state.track.sols, p.sol)];
      const marker = L.circleMarker(point, {radius:6, color:'#ffdfaa', weight:2, fillColor:'#9450e8', fillOpacity:.9});
      // Explicitly approximate location by time; exact camera coordinates are not claimed.
      marker.bindTooltip(p.name + ' · Sol ' + p.sol + ' (ubicación aproximada por sol)');
      marker.on('click', function(){ openPanorama(p.id); });
      marker.addTo(state.map);
      state.panoMarkers.push(marker);
    });
  }
  function progressCoords(coords, last) {
    const step = Math.max(1, Math.ceil((last + 1) / 4500));
    const result = [];
    for (let i = 0; i <= last; i += step) result.push(coords[i]);
    if (!result.length || result[result.length - 1] !== coords[last]) result.push(coords[last]);
    return result;
  }
  function selectSol(request, focus) {
    const track = state.track;
    if (!track) return;
    const sol = Math.max(track.sols[0], Math.min(track.sols[track.sols.length-1], Number(request)));
    const index = nearestIndex(track.sols, sol);
    state.selectedSol = track.sols[index];
    const pos = track.coords[index];
    state.roverMarker.setLatLng(pos);
    state.progressLine.setLatLngs(progressCoords(track.coords, index));
    id('curiosity-sol-slider').value = String(Math.round(state.selectedSol));
    id('curiosity-sol-input').value = String(Math.round(state.selectedSol));
    text('curiosity-sol-label', 'SOL ' + formatNum(Math.round(state.selectedSol)));
    text('curiosity-pos-label', pos[0].toFixed(5) + '° lat · ' + pos[1].toFixed(5) + '° lon');
    text('curiosity-year-note', track.sourceKind === 'full'
      ? 'Fecha entre waypoints interpolada; no indica toma de imagen ni parada exacta.'
      : 'Fecha de parada NASA; entre paradas la línea es una unión recta aproximada.');
    const photoUrl = id('curiosity-raw-images');
    photoUrl.href = sourceUrlForSol(state.selectedSol);
    if(state.rawSol!==Math.round(state.selectedSol)) {state.rawSol=null;state.rawPage=0;text('curiosity-photo-feed-status','Pulsa «Cargar fotos reales» para consultar las fotografías NASA de este sol.');}
    if (focus) state.map.setView(pos, Math.max(state.map.getZoom(), 12));
    id('curiosity-restart').disabled = index === 0;
    id('curiosity-latest').disabled = index === track.coords.length-1;
  }
  function renderTrail(track) {
    state.track = track;
    state.allLine.setStyle({dashArray:track.sourceKind==='waypoints'?'6 9':null});
    state.allLine.setLatLngs(track.coords);
    const bounds = L.latLngBounds(track.coords);
    state.map.fitBounds(bounds.pad(.09), {padding:[18,18], maxZoom:14});
    id('curiosity-sol-slider').min = String(Math.floor(track.sols[0]));
    id('curiosity-sol-slider').max = String(Math.ceil(track.sols[track.sols.length-1]));
    id('curiosity-sol-input').min = String(Math.floor(track.sols[0]));
    id('curiosity-sol-input').max = String(Math.ceil(track.sols[track.sols.length-1]));
    text('curiosity-point-count', formatNum(track.coords.length));
    text('curiosity-max-sol', formatNum(Math.round(track.sols[track.sols.length-1])));
    text('curiosity-trace-length', (track.geometryM / 1000).toFixed(2) + ' km');
    text('curiosity-last-update', track.fetched);
    text('curiosity-source-description', track.attribution + ' ' + track.notes);
    text('curiosity-map-caption', track.sourceKind === 'full'
      ? 'Trayectoria histórica NASA/JPL-Caltech, compilación azmth.space. Sols intermedios interpolados. Base cartográfica: NASA Mars Trek, HiRISE + CTX + Viking (capas por cobertura, sin detalle inventado).'
      : 'MODO DEGRADADO: paradas NASA unidas por segmentos rectos. NO representan el trazado real de las ruedas; la compilación completa no está disponible.');
    drawPanoMarkers();
    selectSol(track.sols[track.sols.length-1], false);
    state.loaded=true;
    id('curiosity-map-loading').hidden=true;
    id('curiosity-reload').disabled=false;
    id('curiosity-play').disabled=false;
    id('curiosity-export').disabled=false;
  }
  function fetchJSON(url, timeoutMs) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, {signal:controller.signal, mode:'cors', cache:'no-store'})
      .then(function(response) {
        if (!response.ok) throw Error('HTTP ' + response.status);
        return response.json();
      }).finally(function() {clearTimeout(timeout);});
  }
  async function loadTrail() {
    if (state.loading) return;
    state.loading = true;
    id('curiosity-reload').disabled = true;
    setStatus('Conectando al recorrido completo de NASA/JPL (compilación azmth.space)...');
    let fullError='';
    try {
      const data = await fetchJSON(FULL_SOURCE, 18000);
      renderTrail(parseTraverse(data));
      setStatus('Recorrido completo cargado · NASA/JPL-Caltech · compilación azmth.space (CC BY 4.0). Fecha de datos: ' + state.track.fetched + '.');
    } catch (e) {
      fullError = e && e.message || String(e);
      setStatus('No se pudo obtener el trazado completo (' + fullError + '). Probando posiciones NASA oficiales...');
      try {
        const data = await fetchJSON(OFFICIAL_WAYPOINTS, 12000);
        renderTrail(parseOfficialWaypoints(data));
        setStatus('Recorrido parcial: paradas documentadas NASA. Las líneas entre puntos NO son la ruta recorrida exacta.');
      } catch (second) {
        id('curiosity-map-loading').hidden=false;
        text('curiosity-map-loading','No se ha podido verificar la trayectoria. Comprueba tu conexión. Fotos 360° y fichas NASA siguen disponibles.');
        setStatus('Sin coordenadas verificadas. Fuente completa: ' + fullError + '. NASA: ' + (second && second.message || second) + '. No se dibujó una trayectoria ficticia.');
        id('curiosity-reload').disabled=false;
      }
    } finally { state.loading=false; }
  }
  function stopPlayback() {
    if (state.timer) { clearInterval(state.timer); state.timer=null; }
    text('curiosity-play', '▶ Recorrer misión');
  }
  function play() {
    if (!state.track) return;
    if (state.timer) { stopPlayback(); return; }
    if (state.selectedSol >= state.track.sols[state.track.sols.length-1]) selectSol(state.track.sols[0], false);
    const range = state.track.sols[state.track.sols.length-1]-state.track.sols[0];
    const increment = Math.max(1, Math.ceil(range / 180));
    state.timer = setInterval(function() {
      const next=state.selectedSol+increment;
      if (next >= state.track.sols[state.track.sols.length-1]) {selectSol(state.track.sols[state.track.sols.length-1], false);stopPlayback();}
      else selectSol(next, false);
    },140);
    text('curiosity-play', '⏸ Pausar');
  }
  function exportTrail() {
    const track = state.track;
    if (!track) return;
    const points = track.coords.map(function(ll) {return [ll[1],ll[0]];});
    const geojson = {type:'FeatureCollection', features:[{
      type:'Feature',properties:{
        rover:'Curiosity', geometrySource:track.attribution, license:track.sourceKind==='full'?'CC BY 4.0 compilation':'NASA source',
        compilationSource:track.sourceKind==='full'?FULL_SOURCE:OFFICIAL_WAYPOINTS,
        fetched:track.fetched, note:track.notes, solFirst:track.sols[0],
        solLast:track.sols[track.sols.length-1]
      },geometry:{type:'LineString', coordinates:points}
    }]};
    const blob = new Blob([JSON.stringify(geojson)], {type:'application/geo+json'});
    const url=URL.createObjectURL(blob);
    const anchor=document.createElement('a');
    anchor.href=url;anchor.download='curiosity-traverse-' + track.sourceKind + '.geojson';
    document.body.appendChild(anchor);anchor.click();anchor.remove();
    setTimeout(function(){URL.revokeObjectURL(url);},2000);
  }

  // Raw NASA photos are individual images, not automatically omnidirectional.

  function importPanoramaFile(file) {
    const status=id('curiosity-import-status');
    if(!file)return;
    if(!['image/jpeg','image/png'].includes(file.type) || file.size>60*1024*1024) {
      status.textContent='Se necesita un JPG o PNG de máximo 60 MB. Divide o reduce mosaicos más grandes con una herramienta de imagen.';
      return;
    }
    if(state.importUrl){URL.revokeObjectURL(state.importUrl);state.importUrl=null;}
    const url=URL.createObjectURL(file);
    state.importUrl=url;
    state.activePano={imported:true,sol:null,image:url};
    text('curiosity-photo-title','Mosaico local experimental · '+file.name);
    text('curiosity-photo-caption','Resultado ensamblado aportado por el usuario. No se ha verificado que cubra 360 grados ni que su cámara tenga una geolocalización exacta. No representa un modelo tridimensional.');
    const source=id('curiosity-photo-source');
    source.href='https://mars.nasa.gov/msl/multimedia/raw-images/';
    source.textContent='Consultar archivo original NASA ↗';
    id('curiosity-photo-dialog').hidden=false;
    const image=id('curiosity-photo-image'),error=id('curiosity-photo-error');
    state.panRatio=.5;state.zoom=1;id('curiosity-zoom').value='1';
    error.hidden=false;error.textContent='Abriendo mosaico local…';
    image.onload=function(){error.hidden=true;positionPhoto();};
    image.onerror=function(){error.hidden=false;error.textContent='No se pudo leer la imagen local.';};
    image.src=url;
    status.textContent='Mosaico importado para previsualización local. La cobertura 360° y la precisión de las uniones siguen sin estar verificadas.';
    if(state.pano3d) {
      state.pano3d.load(url).then(function(ok){
        if(ok && state.activePano?.image===url) {
          error.hidden=true;
          text('curiosity-photo-caption','Vista cilíndrica inmersiva basada en el mosaico local. La imagen procede de los archivos seleccionados por el usuario; no hay terreno ni fotografías generadas artificialmente. Cobertura completa: SIN VERIFICAR.');
        }
      }).catch(function(){if(state.activePano?.image===url)status.textContent='La imagen no tiene el formato necesario para proyección cilíndrica; puedes explorarla como fotografía plana.';});
    }
  }

  function showRawPhoto(photo) {
    stopPlayback();
    state.activePano={raw:true,sol:photo.sol,source:photo.url,url:photo.url};
    document.querySelectorAll('.curiosity-panorama-item').forEach(function(b){b.classList.remove('active');});
    text('curiosity-photo-title',(photo.camera||'Cámara NASA')+' · Sol '+(photo.sol??'?'));
    text('curiosity-photo-caption','Fotografía individual original NASA/JPL-Caltech, sin proyección 360° ni coordenadas de cámara verificadas. Para construir un panorama correcto se requieren múltiples tomas solapadas del mismo punto e información de calibración.');
    id('curiosity-photo-source').href=photo.url;
    id('curiosity-photo-source').textContent='Abrir fotografía NASA ↗';
    id('curiosity-photo-dialog').hidden=false;
    state.panRatio=.5;state.zoom=1;id('curiosity-zoom').value='1';
    const error=id('curiosity-photo-error');
    error.hidden=false;error.textContent='Cargando fotografía original NASA…';
    const img=id('curiosity-photo-image');
    img.onload=function(){error.hidden=true;positionPhoto();};
    img.onerror=function(){error.hidden=false;error.textContent='Esta imagen no se pudo cargar; pulsa «Abrir original NASA».';};
    img.src=photo.url;
    if(state.pano3d)state.pano3d.disable();
  }
  function renderRawPhotos() {
    const grid=id('curiosity-raw-grid');
    grid.textContent='';
    for(const photo of state.rawPhotos) {
      const button=document.createElement('button');
      button.className='curiosity-raw-card';
      button.type='button';
      button.title='Abrir foto NASA; imagen individual, no panorámica 360°';
      const image=document.createElement('img');
      image.loading='lazy'; image.decoding='async'; image.src=photo.url;
      image.alt=(photo.camera||'Cámara NASA')+' • Sol '+(photo.sol??'?');
      image.onerror=function(){image.style.display='none';};
      const label=document.createElement('span');
      const camera=document.createElement('strong');camera.textContent=photo.camera||'NASA Curiosity';
      const sol=document.createElement('small');sol.textContent=' · Sol '+(photo.sol??'?')+' · imagen individual';
      label.append(camera,sol);button.append(image,label);
      button.addEventListener('click',function(){showRawPhoto(photo);});
      grid.append(button);
    }
  }
  async function loadRawPhotos(page=0) {
    if(!state.track){text('curiosity-photo-feed-status','Primero carga la trayectoria para identificar un sol.');return;}
    const sol=Math.round(state.selectedSol), camera=id('curiosity-camera-select').value;
    const request=++state.rawRequest;
    state.rawPage=page;state.rawSol=sol;
    id('curiosity-raw-grid').textContent='';
    text('curiosity-photo-feed-status','Consultando archivo NASA • Sol '+sol+' • página '+(page+1)+'…');
    id('curiosity-photos-prev').disabled=true;
    id('curiosity-photos-next').disabled=true;
    try{
      const response=await fetchJSON(curiosityPhotosURL(sol,camera,page),18000);
      if(request!==state.rawRequest)return;
      const normalized=normalizeRawPhotos(response);
      state.rawPhotos=normalized.photos;
      renderRawPhotos();
      text('curiosity-photo-feed-status',normalized.photos.length
        ? normalized.photos.length+' imágenes originales recibidas de NASA para el sol '+sol+
          (normalized.total!==null?' · '+formatNum(normalized.total)+' resultados disponibles':'')
        : 'Sin imágenes accesibles con esos filtros. Abre el archivo NASA para ampliar la búsqueda.');
      text('curiosity-photos-page','Página '+(page+1));
      id('curiosity-photos-prev').disabled=page===0;
      id('curiosity-photos-next').disabled=normalized.total!==null
        ? (page+1)*24>=normalized.total
        : normalized.photos.length<24;
    }catch(e){
      if(request!==state.rawRequest)return;
      state.rawPhotos=[];
      text('curiosity-photo-feed-status','No fue posible consultar el API de NASA ('+(e.message||e)+'). Usa «Archivo NASA completo» para este sol.');
      id('curiosity-photos-prev').disabled=page===0;
      id('curiosity-photos-next').disabled=true;
    }
  }

  function renderPanoList() {
    const list=id('curiosity-panorama-list');
    list.textContent='';
    PANORAMAS.forEach(function(p) {
      const b=document.createElement('button');
      b.type='button';b.className='curiosity-panorama-item';
      const inner=document.createElement('span');
      const name=document.createElement('strong');
      name.textContent=p.name;
      const meta=document.createElement('small');
      meta.textContent='Sol ' + p.sol + (p.endSol ? '–'+p.endSol : '') + ' · ' + p.year + ' · ' + p.camera;
      inner.append(name,meta);b.appendChild(inner);
      b.dataset.panorama=p.id;
      b.addEventListener('click',function(){openPanorama(p.id);});
      list.appendChild(b);
    });
    text('curiosity-panorama-count', String(PANORAMAS.length));
  }
  function positionPhoto() {
    const img=id('curiosity-photo-image'), wrap=id('curiosity-photo-window');
    if (!img.naturalWidth || !img.naturalHeight) return;
    const height=Math.max(wrap.clientHeight,1)*state.zoom;
    const width=Math.max(wrap.clientWidth,img.naturalWidth/img.naturalHeight*height);
    img.style.height=height+'px';img.style.width=width+'px';
    img.style.left=((wrap.clientWidth-width)*state.panRatio)+'px';
    img.style.top=((wrap.clientHeight-height)/2)+'px';
    img.style.transform='none';
  }
  function closePanorama() {
    id('curiosity-photo-dialog').hidden=true;
    id('curiosity-photo-image').removeAttribute('src');
    id('curiosity-photo-image').onload=null;
    state.activePano=null;
    state.dragging=false;
    if(state.pano3d)state.pano3d.disable();
    if(state.importUrl){ URL.revokeObjectURL(state.importUrl);state.importUrl=null; }
    document.querySelectorAll('.curiosity-panorama-item').forEach(function(b){b.classList.remove('active');});
  }
  function openPanorama(panoId) {
    const p=PANORAMAS.find(function(v){return v.id===panoId;});
    if (!p) return;
    stopPlayback();
    state.activePano=p;
    if (state.track && p.sol>=state.track.sols[0] && p.sol<=state.track.sols[state.track.sols.length-1]) selectSol(p.sol,true);
    document.querySelectorAll('.curiosity-panorama-item').forEach(function(b){b.classList.toggle('active',b.dataset.panorama===p.id);});
    text('curiosity-photo-title',p.name+' · SOL '+p.sol);
    text('curiosity-photo-caption',p.camera+'. '+p.note+' El punto del mapa procede del recorrido por sol, NO de una geolocalización independiente de la cámara.');
    id('curiosity-photo-source').href=p.source;
    id('curiosity-photo-source').textContent='Abrir panorámica original NASA ↗';
    id('curiosity-photo-dialog').hidden=false;
    state.zoom=1;state.panRatio=.5;id('curiosity-zoom').value='1';
    const photo=id('curiosity-photo-image'),err=id('curiosity-photo-error');
    photo.onload=function(){ err.hidden=true; positionPhoto(); };
    photo.onerror=function(){err.hidden=false;err.textContent='No se pudo mostrar una versión ligera del panorama. Abre la ficha original de NASA usando el enlace superior.';};
    if (p.image) {
      err.hidden=false;err.textContent='Cargando panorama original NASA…';
      photo.src=p.image;
      // Immersive cylindrical projection uses NASA's own panorama. It only runs
      // when image CORS, WebGL2 and a panoramic aspect ratio are available.
      // The ordinary scrollable image remains a lossless fallback.
      if (state.pano3d) {
        state.pano3d.load(p.image).then(function(ready){
          if(ready && state.activePano===p){
            err.hidden=true;
            text('curiosity-photo-caption',p.camera+'. '+p.note+
              ' Vista cilíndrica 360° real: arrastra para girar, rueda del ratón para cambiar el campo de visión. No existe profundidad 3D reconstruida.');
          }
        }).catch(function(){
          if(state.activePano===p)text('curiosity-photo-caption',p.camera+'. '+p.note+
            ' Vista 360° horizontal en modo imagen: mueve el ratón o arrastra de izquierda a derecha. La proyección WebGL depende del acceso CORS del servidor NASA.');
        });
      }
    } else {
      photo.removeAttribute('src');
      err.hidden=false;err.textContent='Esta panorámica NASA no dispone aquí de imagen directa verificable. Pulsa «Abrir original NASA» para ver la versión oficial.';
    }
  }
  async function openExplorer() {
    id('curiosity-explorer').hidden=false;
    id('tab-curiosity').setAttribute('aria-pressed','true');
    id('tab-explorer').setAttribute('aria-pressed','false');
    id('tab-jezero').setAttribute('aria-pressed','false');
    state.overlayOpen=true;
    createMap();
    if (!state.map) return;
    setTimeout(function(){state.map.invalidateSize();},60);
    if (!state.loaded && !state.loading) await loadTrail();
  }
  function closeExplorer() {
    stopPlayback();closePanorama();
    id('curiosity-explorer').hidden=true;
    id('tab-curiosity').setAttribute('aria-pressed','false');
    id('tab-explorer').setAttribute('aria-pressed',String(typeof APP==='undefined'||APP.section!=='jezero'));
    id('tab-jezero').setAttribute('aria-pressed',String(typeof APP!=='undefined'&&APP.section==='jezero'));
    state.overlayOpen=false;
  }
  function init() {
    if (!id('tab-curiosity') || !id('curiosity-explorer')) return;
    renderPanoList();
    if (root.CuriosityPano360) {
      state.pano3d=new root.CuriosityPano360(id('curiosity-photo-canvas'));
    }
    id('tab-curiosity').addEventListener('click',openExplorer);
    id('curiosity-close').addEventListener('click',closeExplorer);
    ['tab-explorer','tab-jezero'].forEach(function(name){
      id(name).addEventListener('click',function(){if (state.overlayOpen) closeExplorer();});
    });
    id('curiosity-reload').addEventListener('click',loadTrail);
    for(const mode of ['hirise','ctx','viking']){
      id('curiosity-layer-'+mode).addEventListener('click',function(){updateMapMode(mode);});
    }
    id('curiosity-load-photos').addEventListener('click',function(){loadRawPhotos(0);});
    id('curiosity-import-file').addEventListener('change',function(e){importPanoramaFile(e.target.files?.[0]);});
    id('curiosity-camera-select').addEventListener('change',function(){if(state.rawSol!==null)loadRawPhotos(0);});
    id('curiosity-photos-prev').addEventListener('click',function(){if(state.rawPage>0)loadRawPhotos(state.rawPage-1);});
    id('curiosity-photos-next').addEventListener('click',function(){loadRawPhotos(state.rawPage+1);});
    id('curiosity-fit').addEventListener('click',function(){
      if (state.map && state.track) state.map.fitBounds(L.latLngBounds(state.track.coords).pad(.08),{padding:[18,18],maxZoom:14});
    });
    id('curiosity-restart').addEventListener('click',function(){if(state.track)selectSol(state.track.sols[0],true);});
    id('curiosity-latest').addEventListener('click',function(){if(state.track)selectSol(state.track.sols[state.track.sols.length-1],true);});
    id('curiosity-sol-slider').addEventListener('input',function(e){stopPlayback();selectSol(Number(e.target.value),false);});
    id('curiosity-sol-input').addEventListener('change',function(e){stopPlayback();selectSol(Number(e.target.value),true);});
    id('curiosity-play').addEventListener('click',play);
    id('curiosity-export').addEventListener('click',exportTrail);
    id('curiosity-photo-close').addEventListener('click',closePanorama);
    id('curiosity-zoom').addEventListener('input',function(e){state.zoom=Number(e.target.value);positionPhoto();});
    const windowEl=id('curiosity-photo-window');
    windowEl.addEventListener('pointerdown',function(e){
      if (!id('curiosity-photo-image').naturalWidth) return;
      state.dragging=true;state.dragStartX=e.clientX;state.dragRatio=state.panRatio;
      windowEl.setPointerCapture(e.pointerId);
    });
    windowEl.addEventListener('pointermove',function(e){
      if (!state.dragging) return;
      const image=id('curiosity-photo-image');
      const width=Math.max(windowEl.clientWidth,image.naturalWidth/image.naturalHeight*windowEl.clientHeight*state.zoom);
      const overflow=width-windowEl.clientWidth;
      if (overflow>0) state.panRatio=Math.max(0,Math.min(1,state.dragRatio-(e.clientX-state.dragStartX)/overflow));
      positionPhoto();
    });
    windowEl.addEventListener('pointerup',function(){state.dragging=false;});
    windowEl.addEventListener('pointercancel',function(){state.dragging=false;});
    root.addEventListener('resize',function(){if(state.activePano)positionPhoto();});
    document.addEventListener('keydown',function(e){
      if (e.key==='Escape' && state.activePano) {closePanorama();e.stopPropagation();}
      else if(e.key==='Escape' && state.overlayOpen) closeExplorer();
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})(typeof window !== 'undefined' ? window : globalThis);
