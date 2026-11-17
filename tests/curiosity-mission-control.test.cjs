'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const test=require('node:test');

require('../curiosity_explorer.js');
require('../curiosity_360_renderer.js');

const {curiosityPhotosURL,normalizeRawPhotos,validatedNASAUrl}=globalThis.CuriosityData;
const root=path.resolve(__dirname,'..');

test('NASA raw images query stays scoped to Curiosity and selected sol',()=>{
  const u=new URL(curiosityPhotosURL(5030,'NAV_LEFT_A',2));
  assert.equal(u.hostname,'mars.nasa.gov');
  assert.equal(u.searchParams.get('condition_1'),'msl:mission');
  assert.equal(u.searchParams.get('condition_2'),'5030:sol:gte');
  assert.equal(u.searchParams.get('condition_3'),'5030:sol:lte');
  assert.equal(u.searchParams.get('page'),'2');
  assert.equal(u.searchParams.get('search'),'|NAV_LEFT_A');
});
test('NASA query rejects nonsensical sol, camera and pages',()=>{
  assert.throws(()=>curiosityPhotosURL(-5),/intervalo/);
  assert.throws(()=>curiosityPhotosURL(500,'UNTRUSTED_CAMERA'),/intervalo/);
  assert.throws(()=>curiosityPhotosURL(500,'all',1000),/intervalo/);
});
test('Photo metadata normalization avoids unsafe source links and duplicates',()=>{
  const sample={items:[
    {sol:4021,img_src:'https://mars.nasa.gov/msl-raw-images/picture.jpg',camera:{name:'NAV_LEFT_A'}},
    {sol:4021,img_src:'https://mars.nasa.gov/msl-raw-images/picture.jpg',camera:{name:'NAV_LEFT_A'}},
    {sol:4021,img_src:'javascript:alert(1)',camera:{name:'NAV_LEFT_A'}},
    {sol:4021,img_src:'https://example.com/photo.jpg'}
  ],total_results:45};
  const data=normalizeRawPhotos(sample);
  assert.equal(data.photos.length,1);
  assert.equal(data.photos[0].sol,4021);
  assert.equal(data.photos[0].camera,'NAV_LEFT_A');
  assert.equal(data.total,45);
  assert.equal(validatedNASAUrl('https://evil.nasa.gov.example.com/'),null);
  assert.equal(validatedNASAUrl('http://mars.nasa.gov/image.jpg'),null);
});
test('NASA image library rejects absent/unknown camera query but handles empty pages',()=>{
  assert.equal(normalizeRawPhotos({items:[]}).photos.length,0);
  assert.equal(normalizeRawPhotos(null).photos.length,0);
  assert.equal(normalizeRawPhotos({data:[{img_src:'https://science.nasa.gov/a.png'}]}).photos.length,1);
});
test('Mission Control HTML loads all JS/CSS with real NASA basemap chooser and archive',()=>{
  const html=fs.readFileSync(path.join(root,'mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html'),'utf8');
  for(const id of ['curiosity-layer-hirise','curiosity-layer-ctx','curiosity-layer-viking','curiosity-raw-grid',
    'curiosity-load-photos','curiosity-camera-select','curiosity-photo-canvas','curiosity-import-file']){
    assert.ok(html.includes('id="'+id+'"'),id);
  }
  for(const file of ['curiosity_360_renderer.js','curiosity_explorer.js','curiosity_pro.css']) {
    assert.ok(html.includes(file),file);
    assert.ok(fs.statSync(path.join(root,file)).size>1000,file);
  }
});
test('NASA Trek uses actual high-resolution HiRISE/CTX PNG layers over Viking',()=>{
  const js=fs.readFileSync(path.join(root,'curiosity_explorer.js'),'utf8');
  assert.match(js,/curiosity_hirise_mosaic\/1.0.0\/default\/default028mm/);
  assert.match(js,/Gale_CTX_BlockAdj_dd\/1.0.0\/default\/default028mm/);
  assert.match(js,/maxNativeZoom:16/);
  assert.match(js,/const HI_BOUNDS/);
  assert.match(js,/const CTX_BOUNDS/);
});
test('GPU panorama engine is present but remains separate from 3D terrain reconstruction',()=>{
  assert.equal(typeof globalThis.CuriosityPano360,'function');
  const js=fs.readFileSync(path.join(root,'curiosity_360_renderer.js'),'utf8');
  assert.match(js,/WebGL2/);
  assert.match(js,/verticalFov/);
  assert.match(js,/formato panorámico cilíndrico/);
});

test('Immersive navigation only steps between documented NASA panorama stations',()=>{
  const js=fs.readFileSync(path.join(root,'curiosity_explorer.js'),'utf8');
  const css=fs.readFileSync(path.join(root,'curiosity_pro.css'),'utf8');
  assert.match(js,/const NAVIGABLE_PANORAMAS = PANORAMAS\.filter/);
  assert.match(js,/function stepDocumentedPanorama/);
  assert.match(js,/ESTACIÓN NASA/);
  assert.match(js,/sin desplazamiento fotográfico continuo/);
  assert.match(js,/requestFullscreen/);
  assert.match(css,/\.curiosity-station-nav/);
  assert.match(js,/e\.key==='ArrowLeft'/);
});

test('Scientific route exports preserve USGS source identity and desktop navigation tabs stay compact',()=>{
  const html=fs.readFileSync(path.join(root,'mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html'),'utf8');
  assert.match(html,/dem_provenance: APP\.activeDem\?\.bothInsideTif/);
  assert.match(html,/sourceSHA256/);
  assert.match(html,/\.section-nav button\.mini-btn \{ width:auto/);
});
