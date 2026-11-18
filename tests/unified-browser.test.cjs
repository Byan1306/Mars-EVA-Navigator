'use strict';
/* End-to-end browser: true NASA Z2 skinned mesh, animation and 1m-style movement
   on authentic precomputed USGS DEM. GPU may be software SwiftShader in CI. */
const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(process.env.WORLD_OUTPUT||'_unified/Mars_EVA_Navigator_Unified');
const evidence=path.resolve('motion_evidence');fs.mkdirSync(evidence,{recursive:true});
const MIME={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript',
 '.json':'application/json','.css':'text/css','.glb':'model/gltf-binary','.jpg':'image/jpeg',
 '.wasm':'application/wasm'};
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){
  res.writeHead(404);res.end();return;
 }
 res.writeHead(200,{'Content-Type':MIME[path.extname(file)]||'application/octet-stream'});
 fs.createReadStream(file).pipe(res);
});
(async()=>{
 let browser=null;
 const out={status:'started',worldReady:false,rigged:false,bones:0,
  footsteps:0,walkMotion:false,screenshot:false,errors:[],requestErrors:[]};
 try{
  if(!fs.existsSync(path.join(root,'assets/astronaut_z2_anatomical_206.glb')))throw Error('No rigged NASA Z2 asset');
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  browser=await chromium.launch({channel:'chrome',headless:true,args:[
   '--no-sandbox','--disable-dev-shm-usage','--enable-webgl',
   '--enable-unsafe-swiftshader','--use-angle=swiftshader','--ignore-gpu-blocklist']});
  const page=await browser.newPage({viewport:{width:1440,height:850}});
  page.on('pageerror',err=>out.errors.push(String(err)));
  page.on('response',response=>{
   if(response.status()>=400)out.requestErrors.push(response.status()+' '+response.url());
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/open_world.html');
  await page.waitForFunction(()=>['ready','error'].includes(document.body.dataset.worldState),
    null,{timeout:90000});
  out.worldReady=(await page.locator('body').getAttribute('data-world-state'))==='ready';
  if(!out.worldReady)throw Error('World failed loading: '+await page.locator('#loadMessage').textContent());
  await page.waitForFunction(()=>document.body.dataset.astronautRigged==='true',
    null,{timeout:90000});
  out.rigged=true;
  await page.locator('#cameraThird').click();
  await page.waitForTimeout(1400);
  await page.waitForFunction(()=>document.body.dataset.astronautMocapTracks==='20',
     null,{timeout:30000});
  out.mocapSource=await page.locator('body').getAttribute('data-astronaut-animation-source');
  out.mocapTracks=Number(await page.locator('body').getAttribute('data-astronaut-mocap-tracks'));
  if(!out.mocapSource?.includes('CMU')||out.mocapTracks!==20)
     throw Error('Human walking source was not actually applied: '+out.mocapSource);
  const before=Number(await page.locator('body').getAttribute('data-astronaut-ik-solves'));
  const frames=path.join(evidence,'human_walk_frames');
  fs.mkdirSync(frames,{recursive:true});
  const poses=new Set();
  await page.keyboard.down('w');
  for(let f=0;f<8;f++){
    await page.waitForTimeout(140);
    poses.add(await page.locator('body').getAttribute('data-astronaut-human-pose'));
    await page.screenshot({path:path.join(frames,'human_'+String(f).padStart(2,'0')+'.png')});
  }
  out.walkMotion=(await page.locator('body').getAttribute('data-astronaut-motion'))!=='idle';
  out.distinctHumanLegPoses=poses.size;
  await page.keyboard.up('w');await page.waitForTimeout(220);
  const after=Number(await page.locator('body').getAttribute('data-astronaut-ik-solves'));
  out.footsteps=after-before;
  if(poses.size<4)throw Error('Human walk not changing femur poses across recorded-motion cycle');
  out.bones=Number(await page.locator('body').getAttribute('data-astronaut-bones'));
  if(out.bones!==206)throw Error('Expected verified 206 anatomical joints');
  // On flat/low-error terrain human mocap must take precedence over unnecessary IK.
  await page.screenshot({path:path.join(evidence,'NASA-Z2-rigged-EVA.png')});
  // Educational diagnostic: make all anatomical joint lines visible on demand.
  await page.keyboard.press('k');
  const anatomyVisible=await page.locator('body').getAttribute('data-astronaut-bone-overlay');
  if(anatomyVisible!=='true')throw Error('206 anatomical joint diagnostic overlay failed to appear');
  await page.waitForTimeout(180);
  await page.screenshot({path:path.join(evidence,'NASA-Z2-anatomy-206-overlay.png')});
  out.anatomyOverlayVerified=true;
  out.screenshot=true;out.status='passed';
 }catch(e){out.status='failed';out.error=String(e.stack||e)}
 finally{
  if(browser)await browser.close();
  server.close();
  fs.writeFileSync(path.join(evidence,'motion-browser-test.json'),JSON.stringify(out,null,2)+'\n');
  console.log(JSON.stringify(out,null,2));
  if(out.status!=='passed')process.exitCode=1;
 }
})().catch(e=>{console.error(e);server.close();process.exitCode=1});
