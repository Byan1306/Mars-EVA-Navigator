'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const root=path.resolve(process.env.REGION_OUTPUT||'_region60km/Jezero_60km');
const evidence=path.resolve('surface_region_60km/_evidence');
fs.mkdirSync(evidence,{recursive:true});
const types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript',
 '.bin':'application/octet-stream','.f32':'application/octet-stream',
 '.json':'application/json','.jpg':'image/jpeg'};
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://127.0.0.1');
 const p=path.resolve(root,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
 if(!p.startsWith(root+path.sep)||!fs.existsSync(p)||!fs.statSync(p).isFile()){
  res.writeHead(404).end();return;
 }
 res.writeHead(200,{'Content-Type':types[path.extname(p)]||'application/octet-stream'});
 fs.createReadStream(p).pipe(res);
});
(async()=>{
 let browser;
 const report={ready:false,triangles:0,labels:0,walked:false,teleported:false,
  errors:[],success:false};
 try{
  if(!fs.existsSync(path.join(root,'terrain_manifest.json')))throw Error('Missing official terrain manifest');
  await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
  browser=await chromium.launch({channel:'chrome',headless:true,args:[
    '--no-sandbox','--disable-dev-shm-usage','--enable-webgl',
    '--enable-unsafe-swiftshader','--use-angle=swiftshader','--ignore-gpu-blocklist']});
  const page=await browser.newPage({viewport:{width:1500,height:900}});
  page.on('pageerror',err=>report.errors.push(String(err)));
  await page.goto('http://127.0.0.1:'+server.address().port+'/region.html',{
    waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>['ready','error'].includes(document.body.dataset.worldState),
    null,{timeout:90000});
  report.ready=(await page.locator('body').getAttribute('data-world-state'))==='ready';
  if(!report.ready)throw Error('World failed loading: '+await page.locator('#loadText').textContent());
  await page.waitForTimeout(2200);
  report.triangles=Number(await page.locator('body').getAttribute('data-triangles'));
  if(!report.triangles)throw Error('No real CTX terrain triangles rendered');
  report.labels=await page.locator('#places .place-row').count();
  if(report.labels<8)throw Error('Missing geological place names');
  const before=await page.locator('#localCoords').textContent();
  await page.keyboard.down('w');await page.waitForTimeout(900);await page.keyboard.up('w');
  await page.waitForTimeout(400);
  report.walked=before!==await page.locator('#localCoords').textContent();
  if(!report.walked)throw Error('WASD failed to move real camera');
  await page.locator('#places .place-row').first().click();
  report.teleported=(await page.locator('#selectedName').textContent())!=='Elige un lugar del mapa';
  if(!report.teleported)throw Error('Geological POI teleport failed');
  await page.waitForTimeout(900);
  report.triangles=Number(await page.locator('body').getAttribute('data-triangles'));
  await page.screenshot({path:path.join(evidence,'Jezero-60km-Chrome.png')});
  report.success=true;
 }catch(err){report.error=String(err.stack||err)}
 finally{
  if(browser)await browser.close();
  server.close();
  fs.writeFileSync(path.join(evidence,'regional-browser-report.json'),
    JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
  if(!report.success)process.exitCode=1;
 }
})().catch(err=>{console.error(err);server.close();process.exitCode=1});
