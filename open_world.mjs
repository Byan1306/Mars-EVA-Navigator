/* Mars EVA Open World — Three.js renderer.
 * Geography and collisions are derived only from USGS/NASA DEM samples;
 * sky, illumination and hypsometric colors are illustrative, never imagery.
 */
import * as THREE from './vendor/three.module.js';
import './open_world_core.js';

const C = globalThis.MarsTerrainCore;
const $ = (id) => document.getElementById(id);
const canvas = $('world');
const overlay = $('loadOverlay');
const toastEl = $('toast');
const keys = new Set();
const cameraModes = ['first','third','fly','orbit','top'];
const labels = {first:'PRIMERA PERSONA',third:'TERCERA PERSONA',fly:'VUELO LIBRE',
  orbit:'CÁMARA ORBITAL',top:'VISTA CENITAL'};
const QUALITY = {
  low: {maxDistance:10000,pixelRatio:1,near:1700,middle:4700,shadows:false},
  balanced: {maxDistance:19000,pixelRatio:1.5,near:3900,middle:9500,shadows:false},
  high: {maxDistance:39000,pixelRatio:2,near:6500,middle:18000,shadows:true}
};
let d, renderer, scene, camera, terrainMaterial, lastChunkUpdate=0, lastHud=0;
let avatar, minimapBase, textureMode='analítico', quality='balanced', mode='first';
let yaw=0.3,pitch=-0.08,orbitDistance=130,verticalSpeed=0,grounded=true;
let pointerEnabled=false,player={x:0,y:0,z:0};
let loaded=false, ticker=null;
const tiles=[];
const clock=new THREE.Clock();
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));

function notice(message) {
  toastEl.textContent=message;
  toastEl.classList.remove('hidden');
  clearTimeout(ticker);
  ticker=setTimeout(()=>toastEl.classList.add('hidden'),3700);
}
function failure(err) {
  $('loadMessage').textContent=String(err.message || err);
  overlay.classList.remove('hidden');
  $('retry').classList.remove('hidden');
  $('dataState').textContent='SIN DEM UTILIZABLE';
  $('enterWorld').classList.add('hidden');
  document.body.dataset.worldState='error';
  document.exitPointerLock?.();
}
async function getData() {
  let errors=[];
  for (const url of ['./jezero_dem_precomputed.json','./api/dem/jezero?size=440']) {
    try {
      const response=await fetch(url,{cache:'no-store'});
      if (!response.ok) throw Error('HTTP '+response.status);
      const data=await response.json();
      return C.readDEM(data);
    } catch(err) { errors.push(url+': '+err.message); }
  }
  throw Error('No hay un DEM real válido. Ejecuta scripts/prepare_dem.py --download ctx --export-json y sirve el sitio. '+errors.join(' · '));
}
async function getRegisteredOrtho() {
  try {
    const res=await fetch('./jezero_ortho_meta.json',{cache:'no-store'});
    if(!res.ok) return null;
    const meta=await res.json();
    if(!Array.isArray(meta.bbox) || meta.bbox.length!==4 ||
       !meta.bbox.every((v,i)=>Number.isFinite(v)&&Math.abs(v-d.bbox[i])<1e-8) ||
       !String(meta.source_url||'').startsWith('https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/') ||
       !(meta.valid_fraction>=0.95)) return null;
    const image=await new THREE.TextureLoader().loadAsync('./jezero_ortho.jpg');
    image.colorSpace=THREE.SRGBColorSpace;
    image.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
    textureMode='ortofoto CTX USGS (~6 m/píxel)';
    return image;
  } catch { return null; }
}
function makeTerrain(row,col,span,step) {
  const geometryData=C.chunk(d,row,col,span,step);
  if(!geometryData.indices.length) return null;
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.BufferAttribute(geometryData.vertices,3));
  geometry.setAttribute('uv',new THREE.BufferAttribute(geometryData.uvs,2));
  geometry.setAttribute('color',new THREE.BufferAttribute(geometryData.colors,3));
  geometry.setIndex(new THREE.BufferAttribute(geometryData.indices,1));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  const mesh=new THREE.Mesh(geometry,terrainMaterial);
  mesh.frustumCulled=true;
  mesh.receiveShadow=QUALITY[quality].shadows;
  scene.add(mesh);
  return mesh;
}
function refreshTiles(force=false) {
  if(!d) return;
  const preset=QUALITY[quality];
  for(const tile of tiles) {
    const middleX=C.xAt(d,tile.col+tile.span/2);
    const middleZ=C.zAt(d,tile.row+tile.span/2);
    const range=Math.hypot(middleX-player.x,middleZ-player.z);
    const visible=range<preset.maxDistance+tile.span*Math.max(d.dx,d.dz);
    const step=range<preset.near?1:range<preset.middle?2:4;
    if(!visible) { if(tile.mesh)tile.mesh.visible=false; continue; }
    if(force||step!==tile.step||!tile.mesh) {
      if(tile.mesh) { scene.remove(tile.mesh);tile.mesh.geometry.dispose(); }
      tile.mesh=makeTerrain(tile.row,tile.col,tile.span,step);
      tile.step=step;
    }
    if(tile.mesh) tile.mesh.visible=true;
  }
}
function createWorld() {
  renderer=new THREE.WebGLRenderer({canvas,antialias:true,powerPreference:'high-performance'});
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure=1.25;
  scene=new THREE.Scene();
  scene.background=new THREE.Color(0x786568);
  scene.fog=new THREE.Fog(0x786568,15000,56000);
  camera=new THREE.PerspectiveCamera(72,1,.15,85000);
  scene.add(new THREE.HemisphereLight(0xffe8d8,0x503f3a,2.1));
  const sun=new THREE.DirectionalLight(0xffe1ba,3.0);
  sun.position.set(-11000,18000,7500);
  sun.castShadow=QUALITY[quality].shadows;
  sun.shadow.mapSize.set(2048,2048);
  sun.shadow.camera.left=-5200;sun.shadow.camera.right=5200;
  sun.shadow.camera.top=5200;sun.shadow.camera.bottom=-5200;
  scene.add(sun);
  const bodyMaterial=new THREE.MeshStandardMaterial({color:0xd6e1e0,roughness:.78});
  avatar=new THREE.Group();
  const suit=new THREE.Mesh(new THREE.CapsuleGeometry(.44,1.1,4,8),bodyMaterial);
  suit.position.y=1.06;avatar.add(suit);
  const helmet=new THREE.Mesh(new THREE.SphereGeometry(.35,12,10),
    new THREE.MeshStandardMaterial({color:0xf5f0e5,roughness:.45}));
  helmet.position.y=1.99;avatar.add(helmet);
  const visor=new THREE.Mesh(new THREE.SphereGeometry(.22,12,9),
    new THREE.MeshStandardMaterial({color:0x31444e,metalness:.35,roughness:.25}));
  visor.position.set(0,1.99,-.24);avatar.add(visor);
  avatar.traverse(obj=>{if(obj.isMesh)obj.castShadow=true});
  scene.add(avatar);
  configureQuality();
  window.addEventListener('resize',resize);
  resize();
}
function resize() {
  if(!renderer) return;
  const w=canvas.clientWidth,h=canvas.clientHeight;
  renderer.setSize(w,h,false);
  camera.aspect=w/Math.max(1,h);
  camera.updateProjectionMatrix();
}
function configureQuality() {
  if(!renderer)return;
  const q=QUALITY[quality];
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,q.pixelRatio));
  renderer.shadowMap.enabled=q.shadows;
  if(d) refreshTiles(true);
  resize();
}
function setCamera(value) {
  if(!cameraModes.includes(value))return;
  if(mode==='fly'&&value!=='fly'&&d) {
    const h=C.sample(d,player.x,player.z);
    if(h===null){notice('No es posible aterrizar fuera de cobertura DEM.');return;}
    player.y=h-d.ref;
  }
  mode=value;
  if(mode==='fly')player.y+=3;
  if(mode==='top')orbitDistance=Math.max(650,orbitDistance);
  if(mode==='orbit')orbitDistance=clamp(orbitDistance,60,2200);
  cameraModes.forEach(name=>{
    const id={first:'cameraFirst',third:'cameraThird',fly:'cameraFly',
      orbit:'cameraOrbit',top:'cameraTop'}[name];
    $(id).classList.toggle('active',name===mode);
  });
  $('viewMode').textContent=labels[mode];
  $('crosshair').style.display=(mode==='top'||mode==='orbit')?'none':'block';
}
function safeGround(x,z) {
  const h=C.sample(d,x,z);
  if(h===null) return null;
  const slope=C.slope(d,x,z);
  if($('safeMode').checked && (slope===null || slope>25)) return null;
  return h;
}
let lastBlockNotice=0;
function updateMotion(dt) {
  if(!loaded || !d)return;
  const f=(keys.has('w')?1:0)-(keys.has('s')?1:0);
  const side=(keys.has('d')?1:0)-(keys.has('a')?1:0);
  const norm=Math.hypot(f,side)||1;
  let speed=mode==='fly'?75:(keys.has('c')?3:12);
  if(keys.has('shift'))speed*=mode==='fly'?3:3;
  const moveX=(Math.sin(yaw)*f+Math.cos(yaw)*side)/norm*speed*dt;
  const moveZ=(-Math.cos(yaw)*f+Math.sin(yaw)*side)/norm*speed*dt;
  const targetX=player.x+moveX,targetZ=player.z+moveZ;
  if(mode==='fly') {
    const under=C.sample(d,targetX,targetZ);
    if(under!==null) {
      player.x=targetX;player.z=targetZ;
      player.y+=Math.sin(pitch)*f/norm*speed*dt;
      if(keys.has(' '))player.y+=speed*dt;
      if(keys.has('c'))player.y-=speed*dt;
      player.y=Math.max(player.y,under-d.ref+1.8);
    }
  } else {
    const h=safeGround(targetX,targetZ);
    if(h!==null) {
      player.x=targetX;player.z=targetZ;
    } else if((moveX||moveZ)&&performance.now()-lastBlockNotice>2400) {
      notice('Límite NoData, borde del DEM o pendiente restringida. Vuela (F) o usa el minimapa.');
      lastBlockNotice=performance.now();
    }
    const elevation=C.sample(d,player.x,player.z);
    if(elevation!==null) {
      const floor=elevation-d.ref;
      if(grounded) {
        player.y=floor;
        if(keys.has(' ')) {verticalSpeed=5.7;grounded=false;}
      } else {
        player.y+=verticalSpeed*dt;
        verticalSpeed-=3.71*dt;
        if(player.y<=floor){player.y=floor;verticalSpeed=0;grounded=true;}
      }
    }
  }
}
function updateCamera() {
  if(!d)return;
  const forward=new THREE.Vector3(Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),
    -Math.cos(yaw)*Math.cos(pitch));
  const lookTarget=new THREE.Vector3(player.x,player.y+1.65,player.z);
  avatar.position.set(player.x,player.y,player.z);
  avatar.rotation.y=-yaw;
  avatar.visible=mode==='third'||mode==='orbit'||mode==='top';
  if(mode==='first'||mode==='fly') {
    camera.position.set(player.x,player.y+(mode==='fly'?1.7:keys.has('c')?1.05:1.7),player.z);
    camera.up.set(0,1,0);
    camera.lookAt(camera.position.clone().add(forward));
  } else if(mode==='third') {
    const distance=11;
    let camX=player.x-Math.sin(yaw)*distance;
    let camZ=player.z+Math.cos(yaw)*distance;
    let camY=player.y+6+Math.sin(-pitch)*7;
    const h=C.sample(d,camX,camZ);
    if(h!==null) camY=Math.max(camY,h-d.ref+2.5);
    camera.position.set(camX,camY,camZ);
    camera.up.set(0,1,0);
    camera.lookAt(lookTarget);
  } else if(mode==='orbit') {
    const distance=orbitDistance;
    const camX=player.x-Math.sin(yaw)*Math.cos(pitch)*distance;
    const camZ=player.z+Math.cos(yaw)*Math.cos(pitch)*distance;
    let camY=player.y+30+Math.sin(-pitch)*distance;
    const h=C.sample(d,camX,camZ);
    if(h!==null)camY=Math.max(camY,h-d.ref+2);
    camera.position.set(camX,camY,camZ);
    camera.up.set(0,1,0);camera.lookAt(lookTarget);
  } else {
    camera.position.set(player.x,player.y+orbitDistance,player.z);
    camera.up.set(0,0,-1);camera.lookAt(player.x,player.y,player.z);
  }
}
function drawMinimap() {
  const map=$('minimap'),context=map.getContext('2d');
  if(!d)return;
  const W=map.width,H=map.height;
  if(!minimapBase) {
    const img=context.createImageData(W,H);
    for(let py=0;py<H;py++) for(let px=0;px<W;px++) {
      const col=Math.min(d.w-1,Math.floor(px/W*d.w));
      const row=Math.min(d.h-1,Math.floor(py/H*d.h));
      const index=row*d.w+col,pos=(py*W+px)*4;
      const color=d.mask[index]?C.shade(d,d.values[index]):[.08,.1,.12];
      for(let i=0;i<3;i++)img.data[pos+i]=Math.round(255*color[i]);
      img.data[pos+3]=255;
    }
    minimapBase=img;
  }
  context.putImageData(minimapBase,0,0);
  const px=(player.x/(d.w*d.dx)+.5)*W,py=(player.z/(d.h*d.dz)+.5)*H;
  context.beginPath();context.arc(px,py,5.5,0,Math.PI*2);
  context.fillStyle='#f6ecd6';context.fill();
  context.lineWidth=2;context.strokeStyle='#1b2933';context.stroke();
  context.beginPath();context.moveTo(px,py);
  context.lineTo(px+Math.sin(yaw)*18,py-Math.cos(yaw)*18);
  context.strokeStyle='#fff8eb';context.lineWidth=2;context.stroke();
}
function updateHud() {
  const {lon,lat}=C.geoAt(d,player.x,player.z);
  const h=C.sample(d,player.x,player.z),degrees=C.slope(d,player.x,player.z);
  $('lon').textContent=lon.toFixed(5)+'°';
  $('lat').textContent=lat.toFixed(5)+'°';
  $('elev').textContent=h===null?'NO DATA':Math.round(h).toLocaleString('es-CR')+' m';
  $('slope').textContent=degrees===null?'NO DATA':degrees.toFixed(1)+'°';
  drawMinimap();
}
function frame() {
  if(!loaded)return;
  requestAnimationFrame(frame);
  const dt=Math.min(clock.getDelta(),.05);
  updateMotion(dt);
  updateCamera();
  const now=performance.now();
  if(now-lastChunkUpdate>700){refreshTiles();lastChunkUpdate=now;}
  if(now-lastHud>140){updateHud();lastHud=now;}
  renderer.render(scene,camera);
}
async function init() {
  try {
    $('retry').classList.add('hidden');
    $('loadMessage').textContent='Leyendo mediciones y construyendo mallas topográficas…';
    if(!C)throw Error('No se pudo iniciar el motor científico.');
    d=await getData();
    if(!canvas.getContext('webgl2'))throw Error('Este navegador no permite WebGL2; activa la aceleración por hardware.');
    createWorld();
    const texture=await getRegisteredOrtho();
    terrainMaterial=new THREE.MeshStandardMaterial({
      color:0xffffff,map:texture,vertexColors:!texture,
      roughness:1,metalness:0,side:THREE.FrontSide
    });
    const start=C.findStart(d);
    player={x:start.x,y:start.height-d.ref,z:start.z};
    for(let r=0;r<d.h-1;r+=32)for(let c=0;c<d.w-1;c+=32)
      tiles.push({row:r,col:c,span:32,step:0,mesh:null});
    refreshTiles(true);
    const src=d.raw.source_url;
    $('cell').textContent=Math.round(d.dx)+'×'+Math.round(d.dz)+' m';
    $('coverage').textContent=(d.validFraction*100).toFixed(1)+'%';
    $('dataState').textContent='DEM MARCIANO ACTIVO';
    $('evidence').textContent=(d.raw.source_sha256?
      'USGS CTX con SHA-256 declarado. ':'DEM cargado; procedencia no verificada localmente. ')+
      'Muestreo original: '+(d.raw.source_resolution_m_approx?.map(x=>Math.round(x)+' m').join(' × ')||'no informado')+
      '. Apariencia: '+textureMode+'. La interpolación NO añade detalle.';
    if(typeof src==='string'&&/^https:\/\/planetarymaps\.usgs\.gov\//.test(src))
      $('sourceLink').href=src;
    loaded=true;
    document.body.dataset.worldState='ready';
    overlay.classList.add('hidden');
    setCamera('first');
    clock.start();
    frame();
  }catch(err) {console.error('Mars World:',err);failure(err);}
}
function initInput() {
  window.addEventListener('keydown',e=>{
    if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement?.tagName))return;
    const key=e.key.toLowerCase();
    if([' ','arrowup','arrowdown'].includes(key))e.preventDefault();
    keys.add(key);
    if(e.repeat)return;
    if(key==='f')setCamera(mode==='fly'?'first':'fly');
    if(key==='v')setCamera(mode==='first'?'third':'first');
    if(key==='r'&&d) {
      const start=C.findStart(d);player={x:start.x,y:start.height-d.ref,z:start.z};
      grounded=true;verticalSpeed=0;notice('Posición restaurada a una celda DEM válida.');
    }
    if(key==='m')$('minimap').closest('.map-panel').classList.toggle('hidden');
  });
  window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
  window.addEventListener('blur',()=>keys.clear());
  document.addEventListener('pointerlockchange',()=>{
    pointerEnabled=document.pointerLockElement===canvas;
    $('enterWorld').classList.toggle('hidden',pointerEnabled||!loaded);
  });
  document.addEventListener('mousemove',e=>{
    if(!pointerEnabled)return;
    yaw-=e.movementX*.0020;
    pitch=clamp(pitch-e.movementY*.0020,-1.45,1.45);
  });
  canvas.addEventListener('click',()=>{if(loaded)canvas.requestPointerLock?.();});
  $('enterWorld').addEventListener('click',()=>{if(loaded)canvas.requestPointerLock?.();});
  canvas.addEventListener('wheel',e=>{
    if(mode!=='orbit'&&mode!=='top')return;
    e.preventDefault();orbitDistance=clamp(orbitDistance*Math.exp(e.deltaY*.0015),20,5000);
  },{passive:false});
  $('infoToggle').addEventListener('click',()=>{
    const panel=$('sciencePanel');panel.classList.toggle('hidden');
    $('infoToggle').setAttribute('aria-expanded',String(!panel.classList.contains('hidden')));
  });
  $('quality').addEventListener('change',e=>{quality=e.target.value;configureQuality()});
  Object.entries({cameraFirst:'first',cameraThird:'third',cameraFly:'fly',
    cameraOrbit:'orbit',cameraTop:'top'}).forEach(([id,value])=>
      $(id).addEventListener('click',()=>setCamera(value)));
  $('retry').addEventListener('click',()=>location.reload());
  $('minimap').addEventListener('click',e=>{
    if(!d||!loaded)return;
    const rect=e.currentTarget.getBoundingClientRect();
    const col=clamp(Math.floor((e.clientX-rect.left)/rect.width*d.w),0,d.w-1);
    const row=clamp(Math.floor((e.clientY-rect.top)/rect.height*d.h),0,d.h-1);
    const x=C.xAt(d,col),z=C.zAt(d,row),height=C.sample(d,x,z);
    if(height===null){notice('Sector sin datos válidos: elige otra ubicación.');return;}
    player={x,y:height-d.ref,z};verticalSpeed=0;grounded=true;
    refreshTiles(true);notice('Destino cargado desde una celda topográfica observada.');
  });
  window.addEventListener('beforeunload',()=>{
    for(const tile of tiles)tile.mesh?.geometry.dispose();
    terrainMaterial?.map?.dispose();terrainMaterial?.dispose();renderer?.dispose();
  });
}
initInput();
init();
