'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../open_world_core.js');

// Synthetic numbers exist ONLY inside tests; they are never published as Mars measurements.
function fixture(w=40,h=40) {
  const bbox=[77.39,18.42,77.47,18.48];
  return {width:w,height:h,bbox,elevation_units:'m',
    coordinate_order:'longitude, latitude',source_file:'unit-test-only.tif',
    elevations:Array.from({length:w*h},(_,i)=>-2700+((i/w)|0)*2+(i%w)*.5),
    valid_fraction:1};
}
test('Mars units and sample centers round-trip (not Earth projection)',()=>{
  const d=M.readDEM(fixture());
  assert.ok(d.dx>0&&d.dx<200);
  for(const [r,c] of [[0,0],[20,30],[39,39]]) {
    const x=M.xAt(d,c),z=M.zAt(d,r),geo=M.geoAt(d,x,z);
    const next=M.pointAt(d,geo.lon,geo.lat);
    assert.ok(Math.abs(next.x-x)<1e-7);
    assert.ok(Math.abs(next.z-z)<1e-7);
    assert.ok(Math.abs(M.sample(d,x,z)-d.values[r*d.w+c])<1e-8);
  }
});
test('Reject Earth or mislabelled coverage without constructing world',()=>{
  const bad=fixture();bad.bbox=[-123,36,-122,37];
  assert.throws(()=>M.readDEM(bad),/Jezero/);
  const bad2=fixture();bad2.elevation_units='ft';
  assert.throws(()=>M.readDEM(bad2),/Unidades/);
});
test('NoData blocks interpolation and LOD patches never bridge missing pixels',()=>{
  const raw=fixture();
  raw.elevations[15*40+14]=null;
  raw.valid_fraction=(1600-1)/1600;
  const d=M.readDEM(raw);
  assert.equal(M.sample(d,M.xAt(d,14),M.zAt(d,15)),null);
  assert.equal(M.missingInBox(d,8,8,20,20),1);
  const full=M.chunk(d,0,0,32,1),coarse=M.chunk(d,0,0,32,8);
  assert.ok(full.indices.length>0);
  assert.ok(coarse.indices.length>0);
  const nCols=5;
  const quadStart=1*nCols+1,quadOther=quadStart+nCols;
  const forbidden=[quadStart,quadStart+1,quadOther,quadOther+1];
  // The coarse 8..16 square (missing pixel 14,15) must contain no triangle.
  for(let i=0;i<coarse.indices.length;i+=3)
    assert.ok(![coarse.indices[i],coarse.indices[i+1],
      coarse.indices[i+2]].every(v=>forbidden.includes(v)));
  assert.ok(coarse.indices.length<4*4*6);
});
test('Movement outside raster is rejected rather than extrapolated',()=>{
  const d=M.readDEM(fixture()),start=M.findStart(d);
  assert.ok(Number.isFinite(start.height));
  assert.equal(M.sample(d,d.w*d.dx,0),null);
  assert.ok(M.slope(d,0,0)!==null);
});
test('Color values represent derived shading, never image data',()=>{
  const d=M.readDEM(fixture());
  for(const color of [M.shade(d,d.min),M.shade(d,d.max)]) {
    assert.equal(color.length,3);
    for(const channel of color)assert.ok(channel>=0&&channel<=1);
  }
});
