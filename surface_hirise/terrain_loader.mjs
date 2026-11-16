/* Authentic Jezero HiRISE terrain loader — NO invented elevations.
 * Works as a standalone module and can be imported into Mars EVA Navigator.
 * Requires an importmap: {"imports":{"three":"./vendor/three.module.js"}}
 */
import * as THREE from 'three';
import {GLTFLoader} from './vendor/loaders/GLTFLoader.js';

export async function createMeasuredJezeroSurface(options={}) {
 const {scene,manifestUrl='./terrain_manifest.json',onProgress=()=>{},
   initialLOD=4,tint=true}=options;
 if(!scene)throw new Error('THREE.Scene is required');
 const manifestAbsolute=new URL(manifestUrl,document.baseURI);
 const baseUrl=new URL('.',manifestAbsolute);
 const fetchAsset=(rel)=>new URL(rel,baseUrl).href;
 const response=await fetch(manifestAbsolute,{cache:'no-store'});
 if(!response.ok)throw new Error('Missing HiRISE provenance manifest: HTTP '+response.status);
 const meta=await response.json();
 if(!Array.isArray(meta.tiles)||!meta.tiles.length||
     meta.elevation_unit!=='m'||meta.geometry_scale_y!==1)
   throw new Error('Unsupported or invalid measured surface manifest');
 const [heightsResponse,maskResponse]=await Promise.all([
   fetch(fetchAsset(meta.height_file.path)),fetch(fetchAsset(meta.mask_file.path))]);
 if(!heightsResponse.ok||!maskResponse.ok)throw Error('Missing authentic 1m height or mask data');
 const [heightBytes,maskBytes]=await Promise.all([
   heightsResponse.arrayBuffer(),maskResponse.arrayBuffer()]);
 const n=meta.height_file.samples_per_side;
 if(heightBytes.byteLength!==n*n*4||maskBytes.byteLength!==n*n)
   throw Error('HiRISE height grid and mask dimensions mismatch');
 const elevations=new Float32Array(heightBytes);
 const mask=new Uint8Array(maskBytes);
 const spacing=meta.local_sample_spacing_m;
 const x0=meta.local_sample_center_origin_m[0];
 const z0=meta.local_sample_center_origin_m[1];
 const ref=meta.elevation_reference_m;
 const group=new THREE.Group();group.name='Jezero HiRISE measured 1m surface';
 scene.add(group);
 const loader=new GLTFLoader(),textureLoader=new THREE.TextureLoader();
 const textureCache=new Map();
 let currentLOD=0,generation=0,tintActive=tint,currentObjects=[],disposed=false;
 const choose=(step)=>{
   if(![1,2,4,8].includes(step))throw Error('LOD step must be 1,2,4 or 8');
   return step;
 };
 function sampleAbsolute(x,z) {
   const u=(x-x0)/spacing[0],v=(z-z0)/spacing[1];
   if(u<0||v<0||u>n-1||v>n-1)return null;
   const c0=Math.floor(u),r0=Math.floor(v),
     c1=Math.min(n-1,c0+1),r1=Math.min(n-1,r0+1);
   const a=r0*n+c0,b=r0*n+c1,c=r1*n+c0,d=r1*n+c1;
   if(!mask[a]||!mask[b]||!mask[c]||!mask[d])return null;
   const tx=u-c0,tz=v-r0;
   return (elevations[a]*(1-tx)+elevations[b]*tx)*(1-tz)+
     (elevations[c]*(1-tx)+elevations[d]*tx)*tz;
 }
 function sampleHeight(x,z) {
   const h=sampleAbsolute(x,z);
   return h===null?null:h-ref;
 }
 function sampleSlopeDegrees(x,z) {
   const west=sampleAbsolute(x-spacing[0],z);
   const east=sampleAbsolute(x+spacing[0],z);
   const north=sampleAbsolute(x,z-spacing[1]);
   const south=sampleAbsolute(x,z+spacing[1]);
   if([west,east,north,south].some(v=>v===null))return null;
   return Math.atan(Math.hypot((east-west)/(2*spacing[0]),
       (south-north)/(2*spacing[1])))*180/Math.PI;
 }
 function materialFor(texture) {
   return new THREE.MeshStandardMaterial({map:texture||null,roughness:1,
     metalness:0,color:texture?(tintActive?0xdca789:0xffffff):0xae7958,
     side:THREE.FrontSide});
 }
 async function textureFor(tile) {
   if(!tile.texture)return null;
   const url=fetchAsset(tile.texture.path);
   if(textureCache.has(url))return textureCache.get(url);
   const result=textureLoader.loadAsync(url).then(t=>{
     t.colorSpace=THREE.SRGBColorSpace;
     t.anisotropy=8;
     return t;
   });
   textureCache.set(url,result);
   return result;
 }
 async function loadStep(step) {
   step=choose(step);
   const ticket=++generation;
   const next=[];
   try {
     // Keep the same LOD at *all* tile boundaries: avoids T-junction cracks.
     for(const [i,tile] of meta.tiles.entries()) {
       const asset=tile.lods.find(e=>e.step===step);
       if(!asset)throw Error('Tile '+tile.id+' has no LOD '+step);
       const [gltf,texture]=await Promise.all([
         loader.loadAsync(fetchAsset(asset.path)),textureFor(tile)]);
       for(const mesh of gltf.scene.children) {
         mesh.traverse(node=>{
           if(node.isMesh) {
             node.material?.dispose?.();
             node.material=materialFor(texture);
             node.receiveShadow=true;
           }
         });
       }
       next.push(gltf.scene);
       onProgress({phase:'mesh',loaded:i+1,total:meta.tiles.length,lod:step});
       if(ticket!==generation||disposed)throw Error('Terrain load superseded');
     }
     // Atomic LOD swap, no missing ground while new tile meshes download.
     for(const old of currentObjects) {
       group.remove(old);
       old.traverse(n=>{if(n.isMesh){n.geometry?.dispose?.();n.material?.dispose?.();}});
     }
     currentObjects=next;
     for(const obj of next)group.add(obj);
     currentLOD=step;
     onProgress({phase:'ready',lod:step,total:meta.tiles.length});
   } catch(err) {
     for(const obj of next)obj.traverse(n=>{if(n.isMesh){
       n.geometry?.dispose?.();n.material?.dispose?.();}});
     throw err;
   }
 }
 function setAppearance({tint:newTint}={}) {
   if(typeof newTint!=='boolean')return;
   tintActive=newTint;
   group.traverse(obj=>{
     if(obj.isMesh&&obj.material)obj.material.color.setHex(
       obj.material.map?(tintActive?0xdca789:0xffffff):0xae7958);
   });
 }
 function dispose() {
   disposed=true;generation++;
   scene.remove(group);
   group.traverse(node=>{
     if(node.isMesh){node.geometry?.dispose?.();node.material?.dispose?.();}
   });
   for(const promise of textureCache.values())promise.then(t=>t.dispose()).catch(()=>{});
   textureCache.clear();
 }
 await loadStep(initialLOD);
 return {group,manifest:meta,referenceElevationM:ref,sampleHeight,
   sampleAbsolute,sampleSlopeDegrees,setLOD:loadStep,setAppearance,
   getLOD:()=>currentLOD,dispose,
   getCoverage:()=>({bbox:meta.geographic_bbox_lonlat,
     valid:meta.photographic_texture.available,
     source:meta.source_dem,sourceOrtho:meta.photographic_texture.source})};
}
