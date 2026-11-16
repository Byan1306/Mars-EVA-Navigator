'use strict';
// Optional visual smoke run against a REAL USGS DEM build. No synthetic planet
// content is served. A failed WebGL context is reported, not silently passed.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const http=require('node:http');
const path=require('node:path');
const {chromium}=require('playwright');

const root=path.resolve(__dirname,'../_site');
const results=path.resolve(__dirname,'../artifacts');
fs.mkdirSync(results,{recursive:true});
const mime={'.html':'text/html','.css':'text/css','.js':'text/javascript',
  '.mjs':'text/javascript','.json':'application/json','.jpg':'image/jpeg'};
const server=http.createServer((req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1');
  let local;
  try {
    const decoded=decodeURIComponent(url.pathname);
    local=path.resolve(root,'.'+(decoded==='/'?'/index.html':decoded));
  } catch {res.writeHead(400).end();return;}
  if(!local.startsWith(root+path.sep) || !fs.existsSync(local) ||
      !fs.statSync(local).isFile()) {res.writeHead(404).end();return;}
  res.writeHead(200,{'Content-Type':mime[path.extname(local)]||'application/octet-stream'});
  fs.createReadStream(local).pipe(res);
});
const launchOptions={channel:'chrome',headless:true,args:[
  '--no-sandbox','--disable-dev-shm-usage',
  '--enable-unsafe-swiftshader','--use-angle=swiftshader',
  '--enable-webgl','--ignore-gpu-blocklist'
]};
(async()=>{
 let browser;
 const report={success:false,screenshot:null,error:null,worldState:null,
   visibleTriangles:null,movementVerified:false,cameraVerified:false,consoleErrors:[]};
 try {
   if(!fs.existsSync(path.join(root,'jezero_dem_precomputed.json')))
     throw Error('A verified USGS DEM must be built before the browser test.');
   await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
   const port=server.address().port;
   browser=await chromium.launch(launchOptions);
   const page=await browser.newPage({viewport:{width:1440,height:850},deviceScaleFactor:1});
   page.on('pageerror',err=>report.consoleErrors.push(String(err)));
   await page.goto('http://127.0.0.1:'+port+'/open_world.html',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>['ready','error'].includes(document.body.dataset.worldState),
     null,{timeout:90000});
   report.worldState=await page.locator('body').getAttribute('data-world-state');
   if(report.worldState!=='ready')
     throw Error('3D viewer initialization failed: '+await page.locator('#loadMessage').textContent());
   await page.waitForTimeout(1200);
   report.visibleTriangles=Number(await page.locator('body').getAttribute('data-visible-triangles'));
   if(!(report.visibleTriangles>0)) throw Error('No visible triangles rendered by WebGL.');
   const lonBefore=await page.locator('#lon').textContent();
   await page.keyboard.down('w');await page.waitForTimeout(750);await page.keyboard.up('w');
   await page.waitForTimeout(350);
   const lonAfter=await page.locator('#lon').textContent();
   const latAfter=await page.locator('#lat').textContent();
   report.movementVerified=lonBefore!==lonAfter;
   if(!report.movementVerified)throw Error('WASD did not change geographic position.');
   await page.locator('#cameraFly').click();
   report.cameraVerified=(await page.locator('#viewMode').textContent()).includes('VUELO');
   if(!report.cameraVerified)throw Error('Flight camera button did not change state.');
   report.coords={lonAfter,latAfter};
   await page.locator('#cameraThird').click();
   await page.waitForTimeout(2000);
   if(fs.existsSync(path.join(root,'assets','astronaut_z2.glb'))) {
     try {
       await page.waitForFunction(()=>document.body.dataset.astronaut==='nasa-z2',
         null,{timeout:20000});
     } catch {
       throw Error('Official NASA astronaut exists but glTF did not load into the WebGL scene.');
     }
   }
   report.astronautModel=await page.locator('body').getAttribute('data-astronaut');
   await page.screenshot({path:path.join(results,'jezero-world-astronaut.png'),fullPage:true});
   report.astronautScreenshot='jezero-world-astronaut.png';
   report.success=true;
   await page.screenshot({path:path.join(results,'jezero-world-ground.png'),fullPage:true});
   await page.locator('#cameraOrbit').click();
   await page.locator('#world').hover();
   await page.mouse.wheel(0,1400);
   await page.waitForTimeout(850);
   await page.screenshot({path:path.join(results,'jezero-world-oblique.png'),fullPage:true});
   report.screenshot='jezero-world-oblique.png';
   report.secondaryScreenshot='jezero-world-ground.png';
   report.textureLabel=await page.locator('#evidence').textContent();
 }catch(err) {
   report.error=String(err.stack||err);
   // A screenshot can show whether this is a visual issue, missing data or GPU failure.
 } finally {
   if(browser)await browser.close();
   server.close();
   fs.writeFileSync(path.join(results,'world-smoke-report.json'),
     JSON.stringify(report,null,2)+'\n');
   process.stdout.write(JSON.stringify(report,null,2)+'\n');
   if(!report.success)process.exitCode=1;
 }
})().catch(err=>{console.error(err);process.exitCode=1;server.close();});
