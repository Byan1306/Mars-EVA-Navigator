'use strict';
// Independent Chrome/WebGL verification against real exported HiRISE data.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const root=path.resolve(process.env.SURFACE_OUTPUT||'_hires_surface/Mars_Jezero_Real_Surface');
const artifacts=path.resolve('surface_hirise/_evidence');
fs.mkdirSync(artifacts,{recursive:true});
const types={'.js':'text/javascript','.mjs':'text/javascript','.json':'application/json',
 '.html':'text/html','.glb':'model/gltf-binary','.png':'image/png',
 '.f32':'application/octet-stream','.bin':'application/octet-stream'};
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){
  res.writeHead(404);res.end();return;
 }
 res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});
 fs.createReadStream(file).pipe(res);
});
(async()=>{
 let browser=null;
 const report={success:false,error:null,consoleErrors:[],assetErrors:[],
  triangles:0,ready:false,walkMoved:false,lodChanged:false};
 try{
  if(!fs.existsSync(path.join(root,'terrain_manifest.json')))
   throw Error('Only a real USGS-exported terrain package may be tested.');
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  browser=await chromium.launch({channel:'chrome',headless:true,args:[
    '--no-sandbox','--disable-dev-shm-usage','--enable-webgl',
    '--enable-unsafe-swiftshader','--use-angle=swiftshader','--ignore-gpu-blocklist']});
  const page=await browser.newPage({viewport:{width:1440,height:850}});
  page.on('pageerror',e=>report.consoleErrors.push(String(e)));
  page.on('response',r=>{if(r.status()>=400)report.assetErrors.push(r.url()+' '+r.status())});
  await page.goto('http://127.0.0.1:'+server.address().port+'/preview.html',
    {waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>['true','false'].includes(
    document.body.dataset.surfaceReady),null,{timeout:120000});
  report.ready=(await page.locator('body').getAttribute('data-surface-ready'))==='true';
  if(!report.ready)
   throw Error('HiRISE viewer failed: '+await page.locator('#status').textContent());
  await page.waitForTimeout(1500);
  report.triangles=Number(await page.locator('body').getAttribute('data-triangles'));
  if(!(report.triangles>0))throw Error('WebGL rendered zero measured terrain triangles.');
  await page.screenshot({path:path.join(artifacts,'hirise-orbital.png')});
  await page.locator('#walk').click();
  await page.waitForTimeout(300);
  const oldX=Number(await page.locator('body').getAttribute('data-camera-x'));
  const oldZ=Number(await page.locator('body').getAttribute('data-camera-z'));
  await page.keyboard.down('w');await page.waitForTimeout(700);await page.keyboard.up('w');
  await page.waitForTimeout(300);
  const newX=Number(await page.locator('body').getAttribute('data-camera-x'));
  const newZ=Number(await page.locator('body').getAttribute('data-camera-z'));
  report.walkMoved=Math.hypot(oldX-newX,oldZ-newZ)>0.01;
  if(!report.walkMoved)throw Error('WASD does not move the ground-level scientific camera.');
  await page.screenshot({path:path.join(artifacts,'hirise-ground.png')});
  await page.locator('#lod2').click();
  await page.waitForFunction(()=>document.querySelector('#lod2').classList.contains('active'),
   null,{timeout:120000});
  report.lodChanged=true;
  report.success=true;
 } catch(err){report.error=String(err.stack||err)}
 finally{
  fs.writeFileSync(path.join(artifacts,'browser_report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
  if(browser)await browser.close();
  server.close();
  if(!report.success)process.exitCode=1;
 }
})().catch(err=>{console.error(err);server.close();process.exitCode=1});
