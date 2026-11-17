/* Mars EVA Navigator — cinematic visualization layer.
 * DEM altitude is unchanged. Procedural rocks, sky, dust and suit are artistic
 * reconstructions, NOT observed hazards or an instrument dataset.
 */
import {GLTFLoader} from './vendor/loaders/GLTFLoader.js';
import {DRACOLoader} from './vendor/loaders/DRACOLoader.js';
import {createAstronautMotion} from './astronaut_motion.mjs';

export function createCinematicLayer({THREE,scene,core,dem,renderer,notify}) {
  const clamp=(a,b,c)=>Math.min(c,Math.max(b,a));
  const PI=Math.PI;
  const hash=(x,z,k=0)=>{
    const n=Math.sin(x*127.1+z*311.7+k*74.7)*43758.5453123;
    return n-Math.floor(n);
  };
  const body = new THREE.Group();
  const stylized=new THREE.Group();
  body.add(stylized);
  scene.add(body);
  const metallic=new THREE.MeshStandardMaterial({color:0x7b7772,metalness:.55,roughness:.35});
  const fabric=new THREE.MeshStandardMaterial({color:0xdad5c8,metalness:.04,roughness:.91});
  const fabricAlt=new THREE.MeshStandardMaterial({color:0xbcbab3,metalness:.06,roughness:.91});
  const rubber=new THREE.MeshStandardMaterial({color:0x4c4f52,roughness:.84});
  const ceramic=new THREE.MeshStandardMaterial({color:0xf0ece1,metalness:.11,roughness:.54});
  const visor=new THREE.MeshPhysicalMaterial({color:0x302724,metalness:.67,
    roughness:.14,clearcoat:1,clearcoatRoughness:.11});
  const orange=new THREE.MeshStandardMaterial({color:0xc36a3e,roughness:.82});
  const dark=new THREE.MeshStandardMaterial({color:0x252c31,metalness:.45,roughness:.53});
  const brass=new THREE.MeshStandardMaterial({color:0xb09262,metalness:.65,roughness:.28});

  function shape(parent,g,m,x,y,z,sx=1,sy=1,sz=1) {
    const mesh=new THREE.Mesh(g,m);
    mesh.position.set(x,y,z);mesh.scale.set(sx,sy,sz);mesh.castShadow=true;
    mesh.receiveShadow=true;parent.add(mesh);return mesh;
  }
  function box(parent,m,x,y,z,w,h,depth,bevel=.02) {
    // Rounded plates read as manufactured rather than blocky cubes.
    const mesh=shape(parent,new THREE.BoxGeometry(w,h,depth),m,x,y,z);
    return mesh;
  }
  const sphere=new THREE.SphereGeometry(1,24,16);
  const cylinder=new THREE.CylinderGeometry(1,1,1,14,1);
  function sphereAt(p,m,x,y,z,sx,sy,sz){return shape(p,sphere,m,x,y,z,sx,sy,sz);}
  function cylAt(p,m,x,y,z,top,bottom,length) {
    return shape(p,new THREE.CylinderGeometry(top,bottom,length,14),m,x,y,z);
  }

  // Core torso, rigid reinforcement, backpack and layered life-support hardware.
  const torso=sphereAt(stylized,fabric,0,1.38,0,.43,.56,.26);
  box(stylized,ceramic,0,1.47,-.18,.71,.57,.12);
  box(stylized,rubber,0,1.19,-.11,.66,.13,.21);
  sphereAt(stylized,fabricAlt,0,.94,.01,.38,.23,.25);
  for(const sign of [-1,1]){
    box(stylized,orange,sign*.295,1.51,-.255,.055,.43,.02);
    sphereAt(stylized,rubber,sign*.35,.97,0,.15,.14,.17);
  }
  box(stylized,fabricAlt,0,1.43,.36,.72,.91,.34);
  box(stylized,ceramic,0,1.45,.56,.65,.72,.18);
  for(let i=0;i<5;i++){
    box(stylized,dark,-.2+i*.1,1.42,.657,.057,.37,.021);
    box(stylized,metallic,-.23+i*.12,1.71,.66,.055,.045,.028);
  }
  box(stylized,orange,0,1.88,.51,.32,.075,.09);
  for(const sign of [-1,1]){
    cylAt(stylized,metallic,sign*.34,1.46,.45,.09,.09,.75);
    box(stylized,rubber,sign*.4,1.05,.46,.15,.35,.21);
    box(stylized,brass,sign*.36,1.05,.60,.10,.06,.04);
  }
  cylAt(stylized,metallic,.29,2.06,.42,.018,.018,.30);
  sphereAt(stylized,brass,.29,2.22,.42,.035,.035,.035);
  // Helmet gasket, metallic ring, shell, photographic-like tinted visor.
  cylAt(stylized,rubber,0,1.91,0,.285,.29,.15);
  sphereAt(stylized,ceramic,0,2.14,-.014,.31,.35,.33);
  sphereAt(stylized,visor,0,2.16,-.275,.256,.231,.098);
  for(const sign of [-1,1]){
    sphereAt(stylized,metallic,sign*.29,2.13,-.04,.075,.11,.095);
    sphereAt(stylized,orange,sign*.30,2.18,-.11,.022,.11,.026);
  }
  const rim=new THREE.Mesh(new THREE.TorusGeometry(.265,.025,8,38,PI*1.24),brass);
  rim.position.set(0,2.13,-.245);rim.rotation.z=PI*.12;stylized.add(rim);
  const limbs={arms:[],legs:[]};
  for(const side of [-1,1]){
    const arm=new THREE.Group();
    arm.position.set(side*.43,1.75,0);
    stylized.add(arm);limbs.arms.push({pivot:arm,side});
    sphereAt(arm,ceramic,side*.07,-.05,0,.21,.21,.22);
    box(arm,orange,side*.23,-.19,0,.07,.16,.25);
    cylAt(arm,fabric,side*.11,-.34,0,.145,.18,.48);
    sphereAt(arm,rubber,side*.11,-.57,0,.135,.13,.135);
    cylAt(arm,fabricAlt,side*.11,-.74,0,.165,.125,.37);
    box(arm,ceramic,side*.11,-.96,-.005,.235,.18,.23);
    sphereAt(arm,rubber,side*.11,-1.08,-.055,.12,.13,.12);
    const leg=new THREE.Group();leg.position.set(side*.205,.88,.03);
    stylized.add(leg);limbs.legs.push({pivot:leg,side});
    sphereAt(leg,fabric,0,-.19,0,.215,.35,.23);
    box(leg,rubber,0,-.39,-.17,.25,.10,.08);
    sphereAt(leg,ceramic,0,-.46,-.03,.2,.13,.20);
    cylAt(leg,fabricAlt,0,-.62,-.03,.16,.185,.34);
    box(leg,rubber,0,-.83,-.07,.27,.11,.26);
    box(leg,ceramic,0,-.91,-.13,.29,.17,.42);
    box(leg,dark,0,-.99,-.14,.32,.07,.46);
    box(leg,orange,0,-.805,-.205,.15,.045,.045);
  }
  // Utility patch, wrist controls, belt clasps.
  box(stylized,dark,0,.98,-.25,.29,.13,.075);
  for(let i=0;i<3;i++) sphereAt(stylized,brass,-.08+i*.08,.98,-.291,.018,.018,.012);

  // NASA Z-2 concept suit from NASA's own 3D Resources; independent simulation.
  // It is static unless its GLB supplies animations, and never claimed to
  // represent a real Mars EVA suit currently deployed on Mars.
  let modelRoot=null,modelController=null,modelState='recreado 3D';
  const loader=new GLTFLoader();
  const draco=new DRACOLoader();
  draco.setDecoderPath('./vendor/draco/');
  draco.setWorkerLimit(2);
  loader.setDRACOLoader(draco);
  fetch('./assets/astronaut_manifest.json',{cache:'no-store'})
    .then(r=>r.ok?r.json():null)
    .then(async manifest=>{
      if(!manifest || manifest.publisher!=='NASA' ||
          !String(manifest.source_url||'').includes('nasa/NASA-3D-Resources')) return;
      const gltf=await loader.loadAsync('./assets/astronaut_z2_anatomical_206.glb');
      const root=gltf.scene;
      const bounds=new THREE.Box3().setFromObject(root);
      const ext=bounds.getSize(new THREE.Vector3());
      if(!Number.isFinite(ext.y)||ext.y<=0.001)throw Error('Traje NASA GLB inválido.');
      const scale=2.12/ext.y;
      root.scale.multiplyScalar(scale);
      root.updateMatrixWorld(true);
      const newBounds=new THREE.Box3().setFromObject(root);
      const center=newBounds.getCenter(new THREE.Vector3());
      root.position.sub(new THREE.Vector3(center.x,newBounds.min.y,center.z));
      // NASA model faces away from the camera when character faces -Z;
      // its source coordinate frame is preserved within this scene root.
      root.rotation.y=Math.PI; // display the backpack toward the third-person camera
      stylized.visible=false;
      body.add(root);
      modelRoot=root;
      modelController=createAstronautMotion({THREE,root,gltf,
        sampleGround:(x,z)=>{const h=core.sample(dem,x,z);return h===null?null:h-dem.ref;},
        quality:'balanced'});
      root.traverse(object=>{
        if(object.isMesh){object.castShadow=true;object.receiveShadow=true;}
      });
      modelState='NASA Z-2 / rig anatómico educativo (206 huesos + IK)';
      document.body.dataset.astronaut='nasa-z2-anatomical-206';
      const evidence=document.getElementById('visualEvidence');
      if(evidence)evidence.textContent='NASA Z-2: geometría auténtica, rig anatómico de 206 huesos (80 axial, 126 apendicular) y animación educativos. No es marcha EVA certificada.';
    })
    .catch(err=>{
      console.warn('Modelo NASA no disponible: se conserva astronauta 3D de respaldo.',err);
      document.body.dataset.astronaut='procedural';
    });

  // A soft contact shadow follows the suit, independent of unverified fine DEM.
  const sc=document.createElement('canvas');sc.width=sc.height=128;
  const ctx=sc.getContext('2d');const gradient=ctx.createRadialGradient(64,64,2,64,64,63);
  gradient.addColorStop(0,'rgba(27,18,17,0.63)');
  gradient.addColorStop(.35,'rgba(28,18,15,0.34)');
  gradient.addColorStop(1,'rgba(35,20,18,0)');
  ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128);
  const shadowTex=new THREE.CanvasTexture(sc);
  const shadow=new THREE.Mesh(new THREE.PlaneGeometry(3.8,2.9),
    new THREE.MeshBasicMaterial({map:shadowTex,transparent:true,depthWrite:false,
      toneMapped:false,opacity:.8,polygonOffset:true,polygonOffsetFactor:-1}));
  shadow.rotation.x=-PI/2;shadow.renderOrder=3;scene.add(shadow);

  // Warm dust scattering and illustrative sun position. NOT a recorded sol sky.
  const sky=new THREE.Mesh(new THREE.SphereGeometry(39000,48,32),
    new THREE.ShaderMaterial({
      side:THREE.BackSide,depthWrite:false,fog:false,
      uniforms:{sunDir:{value:new THREE.Vector3(.32,.3,-.9).normalize()}},
      vertexShader:`varying vec3 vDir;void main(){vDir=position;
        gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader:`varying vec3 vDir;uniform vec3 sunDir;
        void main(){
        vec3 d=normalize(vDir);
        float h=smoothstep(-.20,.94,d.y);
        vec3 horizon=vec3(.69,.39,.33);
        vec3 upper=vec3(.35,.26,.32);
        vec3 col=mix(horizon,upper,h);
        col+=vec3(.12,.07,.047)*pow(1.-max(d.y,0.),3.);
        float glow=pow(max(dot(d,sunDir),0.),18.);
        col+=vec3(.47,.24,.11)*glow*.65;
        float corona=pow(max(dot(d,sunDir),0.),1500.);
        col+=vec3(.42,.32,.22)*corona;
        float sun=step(.99982,dot(d,sunDir));
        col=mix(col,vec3(1.,.93,.78),sun);
        gl_FragColor=vec4(col,1.);
      }`
    }));
  sky.frustumCulled=false;sky.renderOrder=-1;scene.add(sky);
  const warmLight=new THREE.DirectionalLight(0xffdbb4,3.6);
  warmLight.position.set(-6000,7600,9000);
  warmLight.castShadow=true;
  warmLight.shadow.mapSize.set(2048,2048);
  warmLight.shadow.camera.left=-18;warmLight.shadow.camera.right=18;
  warmLight.shadow.camera.top=18;warmLight.shadow.camera.bottom=-18;
  warmLight.shadow.camera.near=.5;warmLight.shadow.camera.far=20000;
  warmLight.shadow.bias=-.00006;
  warmLight.shadow.normalBias=.025;
  scene.add(warmLight);
  scene.add(new THREE.HemisphereLight(0xffd5b1,0x58362d,1.75));
  const fillLight=new THREE.DirectionalLight(0xc2d0dd,.65);
  fillLight.position.set(2500,3800,-5200);scene.add(fillLight);
  scene.fog=new THREE.Fog(0xac7366,3800,31000);

  // Procedural *appearance* only: this noise is not elevation and never
  // enters DEM interpolation, route calculations, or the walking collider.
  function makeGrain() {
    const canvas=document.createElement('canvas');canvas.width=canvas.height=256;
    const context=canvas.getContext('2d');
    const img=context.createImageData(256,256);
    for(let y=0;y<256;y++)for(let x=0;x<256;x++){
      const n=hash(x,y),f=hash(Math.floor(x/7),Math.floor(y/7),3);
      const ripple=Math.sin((x+y*.35)*.34);
      const c=clamp(.47+.22*(n-.5)+.22*(f-.5)+.042*ripple,0,1);
      const idx=4*(y*256+x);
      img.data[idx]=Math.round(205*c+44);
      img.data[idx+1]=Math.round(143*c+44);
      img.data[idx+2]=Math.round(101*c+38);
      img.data[idx+3]=255;
    }
    context.putImageData(img,0,0);
    const tex=new THREE.CanvasTexture(canvas);
    tex.wrapS=tex.wrapT=THREE.RepeatWrapping;
    tex.colorSpace=THREE.SRGBColorSpace;
    tex.anisotropy=4;
    return tex;
  }
  const grains=makeGrain();
  function enhanceMaterial(material) {
    material.onBeforeCompile=(shader)=>{
      shader.uniforms.marsGrain={value:grains};
      shader.vertexShader='varying vec3 vMarsWorld;\n'+shader.vertexShader;
      shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>',
        '#include <begin_vertex>\n vMarsWorld=(modelMatrix*vec4(position,1.0)).xyz;');
      shader.fragmentShader='varying vec3 vMarsWorld;\nuniform sampler2D marsGrain;\n'+shader.fragmentShader;
      shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',
        `#include <map_fragment>
        vec3 granular=texture2D(marsGrain,vMarsWorld.xz*.16).rgb;
        float nearFactor=1.-smoothstep(30.,580.,distance(vMarsWorld,cameraPosition));
        diffuseColor.rgb=mix(diffuseColor.rgb,diffuseColor.rgb*(.60+granular*.58),nearFactor*.62);
        `);
    };
    material.needsUpdate=true;
  }

  // Near-field rock props using GPU instancing. NOT mapped rover-visible rocks.
  // Deterministic hash creates stable positions during traversal.
  const rockGeo=new THREE.IcosahedronGeometry(1,1);
  const vertices=rockGeo.attributes.position;
  for(let i=0;i<vertices.count;i++){
    let x=vertices.getX(i),y=vertices.getY(i),z=vertices.getZ(i);
    const warp=.82+hash(i,9)*.44;
    vertices.setXYZ(i,x*warp,y*warp,z*warp);
  }
  rockGeo.computeVertexNormals();
  const large=new THREE.InstancedMesh(rockGeo,new THREE.MeshStandardMaterial({
    color:0xffffff,metalness:.025,roughness:.98,flatShading:true}),3000);
  large.castShadow=false;large.receiveShadow=true;
  large.frustumCulled=false;scene.add(large);
  const dummy=new THREE.Object3D();
  const tint=new THREE.Color();
  let rockAnchorX=Infinity,rockAnchorZ=Infinity;
  let lastQuality='balanced',visualsEnabled=true;
  function placeRocks(player,quality='balanced',force=false) {
    const enabled=document.getElementById('visualDetail')?.checked!==false;
    if(!enabled){large.count=0;visualsEnabled=false;return;}
    if(!force&&enabled===visualsEnabled&&quality===lastQuality&&
       Math.hypot(player.x-rockAnchorX,player.z-rockAnchorZ)<70)return;
    visualsEnabled=enabled;lastQuality=quality;
    rockAnchorX=player.x;rockAnchorZ=player.z;
    const cell=quality==='low'?19:quality==='high'?9:13;
    const radius=quality==='low'?160:quality==='high'?290:215;
    const ax=Math.floor(player.x/cell),az=Math.floor(player.z/cell);
    let count=0;
    const grid=Math.ceil(radius/cell);
    for(let iz=-grid;iz<=grid;iz++)for(let ix=-grid;ix<=grid;ix++){
      const gx=ax+ix,gz=az+iz;
      const x=(gx+hash(gx,gz,1)) *cell;
      const z=(gz+hash(gx,gz,2)) *cell;
      if(Math.hypot(x-player.x,z-player.z)>radius)continue;
      const y=core.sample(dem,x,z);
      if(y===null)continue;
      if(count>=large.instanceMatrix.count)continue;
      const r=hash(gx,gz,3);
      const size=(r>.96?1.1+r*.6:r>.76?.32+r*.55:.07+r*.24);
      dummy.position.set(x,y-dem.ref+size*.26,z);
      dummy.rotation.set(hash(gx,gz,4)*.33,hash(gx,gz,5)*PI*2,hash(gx,gz,6)*.23);
      dummy.scale.set(size*1.12,size*(.34+.34*hash(gx,gz,7)),size*.90);
      dummy.updateMatrix();
      large.setMatrixAt(count,dummy.matrix);
      const hue=hash(gx,gz,8);
      tint.setRGB(.26+hue*.19,.16+hue*.13,.13+hue*.095);
      large.setColorAt(count,tint);
      count++;
    }
    large.count=count;
    large.instanceMatrix.needsUpdate=true;
    if(large.instanceColor)large.instanceColor.needsUpdate=true;
  }

  let time=0;
  function update({dt,player,camera,mode,moving,quality}) {
    time+=dt;
    body.position.set(player.x,player.y,player.z);
    body.rotation.y=player.yaw??0;
    const intensity=moving?1:0;
    if(!modelRoot){
      const stride=time*(moving?7:1.7);
      limbs.legs.forEach(({pivot,side})=>{pivot.rotation.x=Math.sin(stride+side*PI/2)*.43*intensity;});
      limbs.arms.forEach(({pivot,side})=>{pivot.rotation.x=-Math.sin(stride+side*PI/2)*.32*intensity;});
      stylized.position.y=.02*Math.sin(time*1.6)+.036*Math.sin(stride*2)*intensity;
    } else {
      // Animated *bones* with real travel speed and DEM-aware two-bone foot IK.
      modelController?.update({dt,player,active:body.visible,fly:mode==='fly',quality});
    }
    sky.position.copy(camera.position);
    shadow.position.set(player.x,player.y+.025,player.z);
    shadow.material.opacity=mode==='fly'?.12:.8;
    warmLight.position.set(player.x-6000,player.y+7600,player.z+9000);
    warmLight.target.position.set(player.x,player.y+1,player.z);
    if(warmLight.target.parent!==scene)scene.add(warmLight.target);
    placeRocks(player,quality,false);
  }
  function setQuality(q){
    warmLight.castShadow=q==='high';
    large.castShadow=false;
    if(q==='low')renderer.shadowMap.enabled=false;
    lastQuality='';
  }
  function dispose(){
    scene.remove(body,shadow,sky,warmLight,fillLight,large);
    rockGeo.dispose();large.material.dispose();
    shadow.geometry.dispose();shadow.material.dispose();shadowTex.dispose();
    sky.geometry.dispose();sky.material.dispose();grains.dispose();draco.dispose();
  }
  document.body.dataset.astronaut='procedural';
  return {avatar:body,enhanceMaterial,update,setQuality,dispose,
    source:'NASA Z-2, when official model available; otherwise detailed procedural suit',
    visualStatus:()=>modelState};
}
