'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

require('../curiosity_explorer.js');
const {parseTraverse, parseOfficialWaypoints, nearestIndex, marsDistanceMeters, PANORAMAS} = globalThis.CuriosityData;

function fixture(n=101) {
  const lon=[],lat=[],sol=[];
  for(let i=0;i<n;i++){lon.push(137.44-0.00001*i);lat.push(-4.59-0.00002*i);sol.push(i+3);}
  return {slug:'curiosity',path:{lon,lat,sol},fetched:'2026-11-15'};
}

test('Parses all source vertices, not a hardcoded illustration',()=>{
  const track=parseTraverse(fixture());
  assert.equal(track.coords.length,101);
  assert.equal(track.sols.at(-1),103);
  assert.equal(track.fetched,'2026-11-15');
  assert.equal(track.sourceKind,'full');
  assert.ok(track.geometryM>0);
  assert.deepEqual(track.coords[0],[-4.59,137.44]);
});

test('Rejects mismatched arrays and wrong rover',()=>{
  const wrong=fixture();wrong.slug='perseverance';
  assert.throws(()=>parseTraverse(wrong),/Curiosity/);
  const short=fixture();short.path.sol.pop();
  assert.throws(()=>parseTraverse(short),/coherentes/);
});

test('Rejects impossible or reverse-dated coordinates',()=>{
  const invalid=fixture();invalid.path.lat[12]=100;
  assert.throws(()=>parseTraverse(invalid),/validación/);
  const reversed=fixture();reversed.path.sol[15]=-3;
  assert.throws(()=>parseTraverse(reversed),/validación/);
});

test('Converts Mars east longitude 0–360 to east -180 to +180',()=>{
  const example=fixture();
  example.path.lon[4]=270;
  const result=parseTraverse(example);
  assert.equal(result.coords[4][1],-90);
});

test('Finds nearest timestamp by binary search',()=>{
  assert.equal(nearestIndex([3,10,30,90],18),1);
  assert.equal(nearestIndex([3,10,30,90],24),2);
  assert.equal(nearestIndex([3,10,30,90],999),3);
  assert.equal(nearestIndex([3,10,30,90],-100),0);
});

test('Official NASA fallback is explicitly only waypoints',()=>{
  const sample={type:'FeatureCollection',features:[]};
  for(let i=0;i<30;i++)sample.features.push({geometry:{type:'Point',coordinates:[137.4+i*0.00001,-4.6-i*0.00001]},properties:{sol:30+i}});
  const track=parseOfficialWaypoints(sample);
  assert.equal(track.coords.length,30);
  assert.equal(track.sourceKind,'waypoints');
  assert.match(track.notes,/NO es el trazado exacto/);
  assert.ok(track.geometryM>0);
});

test('Panorama source records are NASA only and chronologically indexed',()=>{
  assert.ok(PANORAMAS.length>=8);
  for(let i=0;i<PANORAMAS.length;i++){
    const pano=PANORAMAS[i];
    assert.ok(pano.sol>0);
    assert.match(pano.source,/^https:\/\/science\.nasa\.gov\//);
    if(pano.image)assert.match(new URL(pano.image).hostname,/(^|\.)nasa\.gov$|^photojournal\.jpl\.nasa\.gov$/);
    if(i>0)assert.ok(pano.sol>PANORAMAS[i-1].sol);
  }
});

test('Main HTML includes independent Curiosity panel and its assets',()=>{
  const root=path.join(__dirname,'..');
  const html=fs.readFileSync(path.join(root,'mars_eva_navigator_guia_de_supervivencia_interplanetaria_nasa_space_apps_2026.html'),'utf8');
  assert.match(html,/id="tab-curiosity"/);
  assert.match(html,/id="curiosity-explorer"/);
  assert.match(html,/id="curiosity-photo-dialog"/);
  assert.match(html,/src="\.\/curiosity_explorer\.js"/);
  assert.match(html,/href="\.\/curiosity_explorer\.css"/);
  assert.ok(fs.statSync(path.join(root,'curiosity_explorer.css')).size>1000);
});

test('Mars distance is finite, symmetric and zero at same location',()=>{
  const a=[-4.59,137.44],b=[-4.60,137.45];
  assert.equal(marsDistanceMeters(a,a),0);
  assert.ok(Math.abs(marsDistanceMeters(a,b)-marsDistanceMeters(b,a))<1e-6);
});
