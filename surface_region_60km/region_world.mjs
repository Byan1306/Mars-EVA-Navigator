/* Jezero 60km: georeferenced scientific terrain + location names.
 * Geometry comes only from the official USGS full-crater CTX elevations.
 * NASA and IAU feature labels have explicit provenance/precision.
 * The color of textures, sky and shading is illustrative.
 */
import * as THREE from 'three';
const $=id=>document.getElementById(id);
const canvas=$('world'),overlay=$('overlay'),status=$('status');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.4;
const scene=new THREE.Scene();scene.background=new THREE.Color(0x775955);
scene.fog=new THREE.Fog(0xa5776d,17000,83000);
const camera=new THREE.PerspectiveCamera(66,1,.1,95000);
scene.add(new THREE.HemisphereLight(0xffd5b8,0x3b2930,2.0));
const sun=new THREE.DirectionalLight(0xffd3aa,2.8);sun.position.set(-22000,35000,20000);scene.add(sun);
const cameraState={x:0,z:0,y:1000,yaw:.35,pitch:-.2};
const sceneGroup=new THREE.Group();scene.add(sceneGroup);
const keys=new Set(),surfaceTiles=new Map(),textureCache=new Map();
let data=null,mask=null,manifest=null,ref=0,n=0,spacing=20;
let mode='fly',isPointer=false,initialized=false,lastT=0,lastChunk=-1,previousPaint=0;
const pointNodes=[],nearest=new THREE.Vector3(),dummy=new THREE.Vector3();
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function info(message){status.textContent=message;}
function sample(x,z) {
 if(!data)return null;
 const col=x/spacing+(n-1)/2,row=z/spacing+(n-1)/2;
 if(row<0||col<0||row>n-1||col>n-1)return null;
 const r=Math.floor(row),c=Math.floor(col),rr=Math.min(r+1,n-1),cc=Math.min(c+1,n-1);
 const ids=[r*n+c,r*n+cc,rr*n+c,rr*n+cc];
 if(ids.some(i=>!mask[i]))return null;
 const tx=col-c,tz=row-r;
 return (data[ids[0]]*(1-tx)+data[ids[1]]*tx)*(1-tz)+
   (data[ids[2]]*(1-tx)+data[ids[3]]*tx)*tz-ref;
}
async function loadOfficial() {
 const response=await fetch('./terrain_manifest.json',{cache:'no-store'});
 if(!response.ok)throw Error('Falta el manifiesto científico del terreno.');
 manifest=await response.json();
 if(manifest.schema_version!=='2.0'||manifest.area_ground_m[0]<50000||
    manifest.area_ground_m[1]<50000||manifest.vertical_exaggeration!==1)
   throw Error('La región no supera el contrato científico de al menos 50km.');
 n=manifest.samples_per_side;
 spacing=manifest.cell_spacing_local_m[0];
 ref=manifest.reference_elevation_m;
 const [heightResponse,maskResponse]=await Promise.all([
  fetch('./'+manifest.height_file.path),fetch('./'+manifest.mask_file.path)]);
 if(!heightResponse.ok||!maskResponse.ok)throw Error('No se han descargado alturas/máscara CTX oficiales.');
 const [heights,masks]=await Promise.all([heightResponse.arrayBuffer(),maskResponse.arrayBuffer()]);
 if(heights.byteLength!==n*n*4||masks.byteLength!==n*n)
   throw Error('Datos truncados o incompatible con el manifiesto.');
 data=new Float32Array(heights);
 mask=new Uint8Array(masks);
 const valid=mask.reduce((a,b)=>a+b,0)/mask.length;
 if(Math.abs(valid-manifest.measured_coverage_fraction)>.0001)
   throw Error('Cobertura NoData distinta al registro científico.');
 $('coverage').textContent=(100*valid).toFixed(1)+'%';
 $('region').textContent=(manifest.area_ground_m[0]/1000)+' × '+(manifest.area_ground_m[1]/1000)+' km';
 $('source').href=manifest.source_url;
 await setupPlaces();
 renderMap();
 initialized=true;
 const middle=sample(0,0);
 cameraState.y=middle===null?1200:middle+1250;
 updateHUD();
 info('DEM CTX oficial activo · fotografías originales: '+manifest.tiles.filter(t=>t.texture).length+'/'+manifest.tiles.length+' sectores');
 document.body.dataset.worldState='ready';
}
function textureFor(tile){
 if(!tile.texture)return Promise.resolve(null);
 const url='./'+tile.texture.path;
 if(!textureCache.has(url)){
  const promise=new THREE.TextureLoader().loadAsync(url).then(texture=>{
   texture.colorSpace=THREE.SRGBColorSpace;
   texture.anisotropy=4;
   return texture;
  }).catch(()=>null);
  textureCache.set(url,promise);
 }
 return textureCache.get(url);
}
function geometryFor(tile,step){
 const r0=tile.row*manifest.samples_per_side/(manifest.tile_count[1]*manifest.samples_per_side); // overridden below
 const rowStart=tile.row*250,colStart=tile.col*250;
 const count=250/step+1,vertices=[],uvs=[],indices=[],colors=[];
 for(let ri=0;ri<count;ri++)for(let ci=0;ci<count;ci++){
  const rr=rowStart+ri*step,cc=colStart+ci*step;
  const i=rr*n+cc,h=mask[i]?data[i]-ref:0;
  vertices.push((cc-(n-1)/2)*spacing,h,(rr-(n-1)/2)*spacing);
  uvs.push(ci/(count-1),1-ri/(count-1));
  const elevation=Math.max(0,Math.min(1,(h+2800)/1900));
  colors.push(.45+elevation*.24,.27+elevation*.20,.20+elevation*.17);
 }
 // One summed-area-table per tile lets any coarse face detect interior NoData.
 const integral=new Uint32Array(252*252);
 for(let r=1;r<=251;r++)for(let c=1;c<=251;c++){
  const k=(rowStart+r-1)*n+colStart+c-1;
  integral[r*252+c]=(mask[k]?0:1)+integral[(r-1)*252+c]+
     integral[r*252+c-1]-integral[(r-1)*252+c-1];
 }
 const empty=(r0,c0,r1,c1)=>{
  const a=r0*252+c0,b=(r1+1)*252+c1+1,c=(r1+1)*252+c0,d=r0*252+c1+1;
  return integral[b]-integral[c]-integral[d]+integral[a]>0;
 };
 for(let ri=0;ri<count-1;ri++)for(let ci=0;ci<count-1;ci++){
  const r=ri*step,c=ci*step;
  if(empty(r,c,r+step,c+step))continue;
  const a=ri*count+ci,b=a+1,l=a+count,d=l+1;
  indices.push(a,l,b,b,l,d);
 }
 if(!indices.length)return null;
 const geometry=new THREE.BufferGeometry();
 geometry.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
 geometry.setAttribute('uv',new THREE.Float32BufferAttribute(uvs,2));
 geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
 geometry.setIndex(indices);geometry.computeVertexNormals();
 return geometry;
}
function tileInfo(tile){
 const x=(tile.col*250+125-(n-1)/2)*spacing;
 const z=(tile.row*250+125-(n-1)/2)*spacing;
 const distance=Math.hypot(cameraState.x-x,cameraState.z-z);
 const step=distance<4200?1:distance<12000?2:distance<25000?5:distance<42000?10:25;
 const radius=Math.hypot(x-cameraState.x,z-cameraState.z);
 return{step,active:radius<45000};
}
function disposeMesh(m){
 sceneGroup.remove(m);
 m.geometry.dispose();m.material.dispose();
}
async function ensureTile(tile){
 const desire=tileInfo(tile),existing=surfaceTiles.get(tile.id);
 if(!desire.active){if(existing){disposeMesh(existing.mesh);surfaceTiles.delete(tile.id);}return;}
 if(existing?.step===desire.step)return;
 if(existing){disposeMesh(existing.mesh);surfaceTiles.delete(tile.id);}
 const geo=geometryFor(tile,desire.step);
 if(!geo)return;
 const mat=new THREE.MeshStandardMaterial({color:0xffffff,vertexColors:true,roughness:1});
 const mesh=new THREE.Mesh(geo,mat);
 sceneGroup.add(mesh);
 surfaceTiles.set(tile.id,{mesh,step:desire.step,texture:null});
 const texture=await textureFor(tile);
 if(!surfaceTiles.has(tile.id)||surfaceTiles.get(tile.id).mesh!==mesh)return;
 if(texture){
  mat.map=texture;mat.vertexColors=false;
  mat.color.setHex(0xd6a28c);mat.needsUpdate=true;
 }
}
let streamIndex=0;
function updateTiles(){
 if(!manifest)return;
 const options=manifest.tiles.map(t=>({...t,...tileInfo(t)})).filter(t=>t.active)
    .sort((a,b)=>Math.hypot(a.col-6,a.row-6)-Math.hypot(b.col-6,b.row-6));
 const wanted=new Set(options.map(t=>t.id));
 for(const [key,entry] of surfaceTiles)if(!wanted.has(key)){
  disposeMesh(entry.mesh);surfaceTiles.delete(key);
 }
 const pending=options.filter(t=>surfaceTiles.get(t.id)?.step!==t.step);
 pending.sort((a,b)=>{
  const da=Math.hypot((a.col*250+125-1500)*spacing-cameraState.x,(a.row*250+125-1500)*spacing-cameraState.z);
  const db=Math.hypot((b.col*250+125-1500)*spacing-cameraState.x,(b.row*250+125-1500)*spacing-cameraState.z);
  return da-db;
 });
 for(const t of pending.slice(0,3))ensureTile(t).catch(err=>console.warn('Tile',t.id,err));
 $('tiles').textContent=String(surfaceTiles.size);
}
function renderMap(){
 const can=$('minimap'),ctx=can.getContext('2d'),w=can.width,h=can.height;
 const image=ctx.createImageData(w,h);
 let min=Infinity,max=-Infinity;
 for(let i=0;i<data.length;i+=19){if(mask[i]){min=Math.min(min,data[i]);max=Math.max(max,data[i]);}}
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const rr=Math.round(y/(h-1)*(n-1)),cc=Math.round(x/(w-1)*(n-1));
  const i=rr*n+cc,o=(y*w+x)*4;
  const c=mask[i]?clamp((data[i]-min)/(max-min||1),0,1):null;
  image.data[o]=c===null?30:Math.round(72+144*c);
  image.data[o+1]=c===null?40:Math.round(44+108*c);
  image.data[o+2]=c===null?45:Math.round(34+94*c);
  image.data[o+3]=255;
 }
 const src=document.createElement('canvas');src.width=w;src.height=h;
 src.getContext('2d').putImageData(image,0,0);window._mapSource=src;
 paintMap();
}
function paintMap(){
 const can=$('minimap'),ctx=can.getContext('2d');
 if(!window._mapSource)return;
 ctx.drawImage(window._mapSource,0,0);
 const w=can.width,h=can.height,half=manifest.area_ground_m[0]/2;
 for(const p of manifest.places){
  if(!p.inside_region)continue;
  const x=(p.x_m+half)/(half*2)*w,z=(p.z_m+half)/(half*2)*h;
  ctx.beginPath();ctx.arc(x,z,3.2,0,Math.PI*2);
  ctx.fillStyle=p.precision.toLowerCase().includes('official')?'#ffe3ae':'#e9d4c5';
  ctx.fill();
 }
 const x=(cameraState.x+half)/(half*2)*w,z=(cameraState.z+half)/(half*2)*h;
 ctx.beginPath();ctx.arc(x,z,5,0,Math.PI*2);ctx.fillStyle='#f8ffed';ctx.fill();
 ctx.strokeStyle='#1b2730';ctx.lineWidth=2;ctx.stroke();
}
async function setupPlaces(){
 const wrap=$('places');
 wrap.innerHTML='';
 for(const p of manifest.places){
  if(!p.inside_region)continue;
  const row=document.createElement('button');
  row.type='button';row.className='place-row';
  const verified=p.precision.toLowerCase().includes('official')||p.precision.includes('published');
  const icon=p.type==='crater'?'◉':p.type==='mission'?'⌖':p.type==='valley'?'⌁':'△';
  row.innerHTML='<span class="place-symbol">'+icon+'</span><span><b></b><small></small></span>';
  row.querySelector('b').textContent=p.name;
  row.querySelector('small').textContent=verified?'Ubicación documentada':'Referencia aproximada';
  row.title=p.detail;
  row.onclick=()=>teleport(p.id);
  wrap.appendChild(row);
  const tag=document.createElement('button');
  tag.className='location-label';tag.type='button';tag.textContent=p.name;
  tag.onclick=()=>teleport(p.id);
  document.getElementById('annotations').appendChild(tag);
  pointNodes.push({point:p,element:tag});
 }
}
function teleport(id){
 const p=manifest.places.find(v=>v.id===id);
 if(!p||!p.has_measured_elevation){
  info('La ubicación no tiene elevación verificada en esta región.');return;
 }
 cameraState.x=p.x_m;cameraState.z=p.z_m;
 const h=sample(p.x_m,p.z_m);
 cameraState.y=(h===null?1300:h)+ (mode==='fly'?730:1.8);
 $('selectedName').textContent=p.name;
 $('selectedInfo').textContent=p.detail+' '+(p.precision.toLowerCase().includes('approximate')?'Pin aproximado.':'');
 $('selectedSource').href=p.source;
 $('selectedSource').hidden=false;
 info('Ubicación seleccionada: '+p.name);
 updateTiles();paintMap();
}
function projectLabels(){
 if(!initialized)return;
 for(const {point:p,element} of pointNodes){
  if(!p.has_measured_elevation){element.style.display='none';continue;}
  const v=new THREE.Vector3(p.x_m,p.elevation_m-ref+40,p.z_m);
  v.project(camera);
  const visible=v.z>-1&&v.z<1&&Math.abs(v.x)<.9&&Math.abs(v.y)<.92;
  element.style.display=visible?'block':'none';
  if(visible){
   element.style.left=((v.x+1)*.5*innerWidth)+'px';
   element.style.top=((-v.y+1)*.5*innerHeight)+'px';
  }
 }
}
function updateHUD(){
 const ground=sample(cameraState.x,cameraState.z);
 $('elevation').textContent=ground===null?'SIN DATOS':Math.round(ground+ref).toLocaleString('es-CR')+' m';
 const coordX=cameraState.x/manifest.area_ground_m[0]*1;
 const coordZ=cameraState.z/manifest.area_ground_m[1]*1;
 $('localCoords').textContent=String(Math.round(cameraState.x))+', '+String(Math.round(cameraState.z))+' m';
 $('flight').textContent=mode==='fly'?'VUELO LIBRE':'CAMINAR';
}
function move(dt){
 const forward=(keys.has('w')?1:0)-(keys.has('s')?1:0);
 const sideways=(keys.has('d')?1:0)-(keys.has('a')?1:0);
 const speed=(mode==='fly'?100:12)*(keys.has('shift')?4:1);
 const theta=cameraState.yaw,norm=Math.max(1,Math.hypot(forward,sideways));
 const x=cameraState.x+(Math.sin(theta)*forward+Math.cos(theta)*sideways)*speed*dt/norm;
 const z=cameraState.z+(-Math.cos(theta)*forward+Math.sin(theta)*sideways)*speed*dt/norm;
 const floor=sample(x,z);
 if(floor!==null){
  cameraState.x=x;cameraState.z=z;
  if(mode==='walk')cameraState.y=floor+1.8;
 }
 if(mode==='fly') {
  cameraState.y+=((keys.has(' ')?1:0)-(keys.has('c')?1:0))*speed*dt;
  cameraState.y+=Math.sin(cameraState.pitch)*forward*speed*dt;
  const h=sample(cameraState.x,cameraState.z);
  if(h!==null)cameraState.y=Math.max(cameraState.y,h+2);
 }
}
function frame(t){
 requestAnimationFrame(frame);
 const dt=Math.min((t-lastT)*.001,.05);lastT=t;
 if(initialized){
  move(dt);
  camera.position.set(cameraState.x,cameraState.y,cameraState.z);
  camera.lookAt(cameraState.x+Math.sin(cameraState.yaw)*Math.cos(cameraState.pitch),
    cameraState.y+Math.sin(cameraState.pitch),
    cameraState.z-Math.cos(cameraState.yaw)*Math.cos(cameraState.pitch));
  if(t-lastChunk>500){updateTiles();lastChunk=t;}
  if(t-previousPaint>250){paintMap();updateHUD();projectLabels();previousPaint=t;}
 }
 renderer.render(scene,camera);
 document.body.dataset.triangles=String(renderer.info.render.triangles);
}
requestAnimationFrame(frame);
function resize(){renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();}
window.addEventListener('resize',resize);resize();
window.addEventListener('keydown',e=>{
 if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;
 keys.add(e.key.toLowerCase());if(e.key===' ')e.preventDefault();
 if(e.key.toLowerCase()==='f'){mode=mode==='fly'?'walk':'fly';$('flight').textContent=mode==='fly'?'VUELO LIBRE':'CAMINAR';}
});
window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
window.addEventListener('blur',()=>keys.clear());
document.addEventListener('pointerlockchange',()=>{
 isPointer=document.pointerLockElement===canvas;
 $('instructions').classList.toggle('hidden',isPointer);
});
canvas.addEventListener('click',()=>{if(initialized)canvas.requestPointerLock?.()});
window.addEventListener('mousemove',e=>{
 if(!isPointer)return;
 cameraState.yaw-=e.movementX*.002;
 cameraState.pitch=clamp(cameraState.pitch-e.movementY*.002,-1.45,1.45);
});
$('minimap').addEventListener('click',e=>{
 if(!manifest)return;
 const rect=e.currentTarget.getBoundingClientRect();
 const x=(e.clientX-rect.left)/rect.width*manifest.area_ground_m[0]-manifest.area_ground_m[0]/2;
 const z=(e.clientY-rect.top)/rect.height*manifest.area_ground_m[1]-manifest.area_ground_m[1]/2;
 const h=sample(x,z);
 if(h===null){info('NoData: no puedo teletransportarte a una celda sin elevación.');return;}
 cameraState.x=x;cameraState.z=z;cameraState.y=h+(mode==='fly'?600:1.8);
});
$('toggleMode').onclick=()=>{mode=mode==='fly'?'walk':'fly';updateHUD()};
$('showLabels').onchange=e=>document.getElementById('annotations').classList.toggle('hidden',!e.target.checked);
$('instructions').onclick=()=>{if(initialized)canvas.requestPointerLock?.()};
loadOfficial().then(()=>{$('loader').classList.add('hidden')}).catch(err=>{
 document.body.dataset.worldState='error';$('loadText').textContent=String(err.message||err);
 console.error('Real USGS regional world',err);
});
