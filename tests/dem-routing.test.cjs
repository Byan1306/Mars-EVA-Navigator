'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html'), 'utf8');
const script = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];

// Run the actual app's numerical code. Only DOM/Leaflet rendering is stubbed;
// test fixtures are never installed as app data or presented as Martian evidence.
function app() {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {textContent:'', className:'', querySelector:()=>({textContent:''})});
    return elements.get(id);
  };
  const context = vm.createContext({
    window:{addEventListener(){}}, document:{getElementById:element},
    setTimeout, clearTimeout, URLSearchParams, console,
  });
  vm.runInContext(script, context);
  return {context, elements, run:code=>vm.runInContext(code, context), load(data, n=data.width) {
    context.payload = data;
    vm.runInContext(`APP.tifDem=validateDemPayload(payload,'UNIT TEST fixture');
      APP.backendUrl=null; APP.section='jezero'; APP.demoTerrain=false;
      APP.isAnalogEarth=false; APP.searchExtent='full'; GRID_N=${n};
      sampleGlobalMolaElevation=()=>{throw new Error('Synthetic terrain must never run');};`,context);
  }};
}
function fixture(n=20) {
  return {width:n,height:n,bbox:[77.40,18.43,77.47,18.47],
    elevations:Array.from({length:n*n},(_,i)=>-2400+Math.floor(i/n)*0.5+(i%n)*0.2),
    crs:'+proj=longlat +R=3396190 +no_defs',elevation_units:'m',
    coordinate_order:'longitude, latitude',pixel_registration:'area',row_order:'north_to_south',
    cell_size_m:150, source_resolution_m:[20,20], provenance:{verified:false,source_product:'test_fixture'}};
}
function routeAt(a,start=[5,5],goal=[14,14]) {
  a.context.startRC=start; a.context.goalRC=goal;
  return a.run(`
    var dem=buildDynamicDem();
    APP.origLatLng=dem.cellToLatLon(...startRC); APP.destLatLng=dem.cellToLatLon(...goalRC);
    var route=computeSingle3DRoute(dem,dem.latLonToCell(...APP.origLatLng),dem.latLonToCell(...APP.destLatLng),'green',getEnvParams(),12.5);
    route;`);
}

test('DEM parser requires Mars coordinates, metre heights, explicit null NoData and valid dimensions',()=>{
  const a=app();
  for(const update of [{crs:'EPSG:4326'},{elevation_units:'ft'},{row_order:'south_to_north'},
      {cell_size_m:0},{source_resolution_m:[20,-1]},{width:2},{valid_fraction:'bogus'},
      {bbox:[77,18,181,19]},{elevations:fixture().elevations.map(()=>null)}]){
    a.context.payload={...fixture(),...update};
    assert.throws(()=>a.run("validateDemPayload(payload,'fixture')"));
  }
  for(const bad of [NaN, Infinity, '-2400', -3.4028226550889045e38]) {
    const data=fixture();data.elevations[0]=bad;a.context.payload=data;
    assert.throws(()=>a.run("validateDemPayload(payload,'fixture')"),/NoData/);
  }
});

test('bilinear sampler preserves known heights, NoData and bounds without edge extrapolation',()=>{
  const a=app(), data=fixture(2);
  data.elevations=[-2400,-2390,-2380,null];a.load(data);
  assert.equal(a.run('sampleTifElevationBilinear(18.46,77.4175)'),-2400);
  assert.ok(Number.isNaN(a.run('sampleTifElevationBilinear(18.44,77.4525)')));
  assert.ok(Number.isNaN(a.run('sampleTifElevationBilinear(18.45,77.49)')));
  assert.ok(Number.isNaN(a.run('sampleTifElevationBilinear(NaN,77.43)')));
});

test('static crop cannot borrow unexported full-raster coverage',()=>{
  const a=app(),data=fixture(); data.full_bbox=[77,18,78,19];a.load(data);
  assert.equal(a.run('planningWindow().minLon'),data.bbox[0]);
  assert.equal(a.run('planningWindow().maxLat'),data.bbox[3]);
  assert.doesNotThrow(()=>a.run('buildDynamicDem()'));
});

test('EVA route elevation and ascent come from the loaded grid, never the procedural generator',()=>{
  const a=app();a.load(fixture());const route=routeAt(a);
  assert.equal(route.executable,true);
  assert.ok(route.elevGainM>0);
  assert.ok(route.elevations.every(z=>z>=-2400 && z<-2380));
  assert.equal(a.run('route.cells.every((cell,i)=>route.elevations[i]===dem.elev[cell.idx])'),true);
  assert.equal(a.run('dem.bothInsideTif'),true);
  const raised=fixture();raised.elevations=raised.elevations.map(z=>z+250);a.load(raised);
  const next=routeAt(a);
  assert.equal(next.executable,true);
  assert.equal(next.elevations[0]-route.elevations[0],250);
});

test('continuous NoData and steep barriers reject routes; no fallback line is fabricated',()=>{
  for(const barrier of [null,-1800]){
    const a=app(),data=fixture();
    for(let row=0;row<20;row++)data.elevations[row*20+10]=barrier;
    a.load(data);const route=routeAt(a,[5,5],[14,14]);
    assert.equal(route.executable,false);
    assert.equal(route.coords.length,0);
    assert.match(route.reason,/No hay/);
  }
});

test('unknown source is not labelled USGS, metadata distinguishes native resolution and mesh',()=>{
  const a=app();a.load(fixture());
  assert.match(a.run('demSourceDescription()'),/20.0 × 20.0 m\/píxel/);
  assert.match(a.run('demSourceDescription()'),/procedencia sin verificar/);
  assert.doesNotMatch(a.run('demSourceDescription()'),/USGS/);
  const invalid=fixture();invalid.provenance={verified:true};a.context.payload=invalid;
  assert.throws(()=>a.run("validateDemPayload(payload,'fixture')"),/procedencia verificada/);
});

test('Jezero refuses to build a grid without DEM coverage',()=>{
  const a=app();
  a.run(`APP.section='jezero'; APP.demoTerrain=true; APP.tifDem=null;
    sampleGlobalMolaElevation=()=>{throw new Error('Synthetic terrain must never run');};`);
  assert.throws(()=>a.run('buildDynamicDem()'),/no se permite terreno sintético/);
});

const realPath=path.join(root,'jezero_dem_precomputed.json');
test('official exported CTX drives the real Jezero default EVA route',()=>{
  const data=JSON.parse(fs.readFileSync(realPath,'utf8')),a=app();
  assert.equal(data.provenance.verified,true);
  assert.equal(data.provenance.source_product,'usgs_ctx');
  assert.deepEqual(data.source_resolution_m,[20,20]);
  a.load(data,160);
  const results=a.run(`APP.searchExtent=1;
    var dem=buildDynamicDem();
    var start=dem.latLonToCell(...APP.origLatLng),goal=dem.latLonToCell(...APP.destLatLng);
    var routes=[['green',12.5],['blue',18.5],['red',24]].map(([profile,limit])=>computeSingle3DRoute(dem,start,goal,profile,getEnvParams(),limit));
    ({real:dem.bothInsideTif,routes});`);
  assert.equal(results.real,true);
  assert.ok(results.routes.some(r=>r.executable),'At least one default EVA profile must find a route on real CTX');
  for(const route of results.routes.filter(r=>r.executable)){
    assert.ok(route.elevations.every(Number.isFinite));
    assert.ok(route.elevations.every(z=>z>=-2800&&z<=-1400));
    a.context.routeToCheck=route;
    assert.equal(a.run('routeToCheck.cells.every((cell,i)=>routeToCheck.elevations[i]===dem.elev[cell.idx])'),true);
  }
});


test('direct browser TIFF imports reject ambiguous units, scale and unsupported georeferencing',()=>{
  const a=app();
  const makeImage=(metadata={UNITTYPE:'m'},resolution=[0.001,-0.001],directory={})=>({
    getResolution:()=>resolution,getFileDirectory:()=>directory,getGDALMetadata:()=>metadata});
  const geoKeys={GTModelTypeGeoKey:2,GeogSemiMajorAxisGeoKey:3396190,GTRasterTypeGeoKey:1};
  a.context.geoKeys=geoKeys;a.context.image=makeImage();
  assert.doesNotThrow(()=>a.run('validateBrowserGeoTiff(image,geoKeys)'));
  for(const image of [makeImage({UNITTYPE:'ft'}),makeImage({}),makeImage({UNITTYPE:'m',SCALE:'0.1'}),
      makeImage({UNITTYPE:'m',OFFSET:'100'}),makeImage({UNITTYPE:'m'},[0.001,0.001]),
      makeImage({UNITTYPE:'m'},[0.001,-0.001],{ModelTransformation:[1]}),
      makeImage({UNITTYPE:'m'},[0.001,-0.001],{SubIFDs:[123]}),
      makeImage({UNITTYPE:'m'},[0.001,-0.001],{NewSubfileType:4})]){
    a.context.image=image;assert.throws(()=>a.run('validateBrowserGeoTiff(image,geoKeys)'));
  }
  a.context.image=makeImage();
  assert.throws(()=>a.run('validateBrowserGeoTiff(image,geoKeys,2)'),/máscaras/);
  for(const update of [{GTRasterTypeGeoKey:2},{GeogSemiMajorAxisGeoKey:6378137},
      {GeogSemiMinorAxisGeoKey:3376200},{VerticalUnitsGeoKey:9002},{GeogAngularUnitsGeoKey:9101}]){
    a.context.geoKeys={...geoKeys,...update};assert.throws(()=>a.run('validateBrowserGeoTiff(image,geoKeys)'));
  }
});
