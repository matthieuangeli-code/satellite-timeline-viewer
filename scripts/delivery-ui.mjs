// UI regressions with SYNTHETIC API responses. This does not validate Stripe or IGN.
import assert from 'node:assert/strict';
import { readFile, mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';
const front='https://sitehistory.test',api='https://api.sitehistory.test';
const key='sitehistory-order',owner={id:'fixture-order',token:'fixture-owner-only',savedAt:Date.now()};
const ready={status:'ready',parcel_id:'276440000B0150',message:'Fixture : paiement vérifié.',downloads:{html:'/fresh/report.html',pdf:'/fresh/report.pdf'}};
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{})});
await mkdir('test-results/delivery-ui',{recursive:true});let passed=0;
async function check(name,stored,states,run){
 const context=await browser.newContext({viewport:{width:390,height:844}});const requests=[];let calls=0;
 try{
  await context.addInitScript(({key,stored})=>{if(stored)localStorage.setItem(key,JSON.stringify(stored))},{key,stored});
  await context.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.origin===api){
    if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':front,'Access-Control-Allow-Headers':'Authorization','Access-Control-Allow-Methods':'GET'}});
    requests.push(u.pathname);
    if(u.pathname.startsWith('/api/orders/')){
     assert.equal(route.request().headers().authorization,'Bearer '+owner.token);
     const state=states[Math.min(calls++,states.length-1)];
     return route.fulfill({status:typeof state.status==='number'?state.status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':front},body:JSON.stringify(state.body||state)});
    }
    if(u.pathname==='/fresh/report.pdf')return route.fulfill({contentType:'application/pdf',headers:{'Access-Control-Allow-Origin':front,'Content-Disposition':'attachment; filename="synthetic-fixture.pdf"'},body:'%PDF-1.7 SYNTHETIC UI FIXTURE'});
    throw Error('Unexpected or stale fixture download');
   }
   if(u.origin===front){
    if(u.pathname==='/assets/config.js')return route.fulfill({contentType:'text/javascript',body:`window.SITEHISTORY_API=${JSON.stringify(api)};`});
    const file=u.pathname==='/demo.html'?'demo.html':u.pathname.slice(1);
    assert.ok(['demo.html','assets/sitehistory.js','assets/sitehistory.css'].includes(file));
    return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html',body:await readFile('docs/'+file)});
   }
   // Maps deliberately unavailable: they must not prevent paid-order recovery.
   return route.fulfill({contentType:u.pathname.endsWith('.css')?'text/css':'text/javascript',body:''});
  });
  const page=await context.newPage();await page.goto(front+'/demo.html?checkout=returned');
  await run(page,requests,()=>calls);await page.screenshot({path:`test-results/delivery-ui/${name}.png`,fullPage:true});
  passed++;console.log('SYNTHETIC delivery UI passed: '+name);
 }finally{await context.close()}
}
try{
 await check('new-tab-and-stale-link',owner,[ready],async(page,requests)=>{
  await page.locator('#delivery a').first().waitFor();assert.equal(await page.evaluate(()=>sessionStorage.getItem('sitehistory-order')),null);
  const box=await page.locator('#delivery').boundingBox();assert.ok(box.y>=0&&box.y+box.height<=844);
  const link=page.getByRole('link',{name:'Télécharger PDF',exact:true});await link.evaluate(a=>a.href='https://api.sitehistory.test/expired/report.pdf');
  const downloading=page.waitForEvent('download');await link.click();const download=await downloading;assert.equal(await download.failure(),null);
  assert.ok(requests.includes('/fresh/report.pdf'));assert.ok(!requests.includes('/expired/report.pdf'));
 });
 await check('retry-after-503',owner,[{status:503,body:{detail:'Stockage temporairement indisponible.'}},ready],async page=>{
  await page.getByText(/Stockage temporairement indisponible/).waitFor();assert.equal(await page.locator('#delivery a').count(),0);
  await page.locator('#refresh-delivery').click();await page.locator('#delivery a').first().waitFor();assert.equal(await page.locator('#delivery a').count(),2);
 });
 await check('expired-server-order',owner,[{status:410,body:{detail:'Dossier expiré après 24 heures.'}}],async page=>{
  await page.getByText(/Dossier expiré après 24 heures/).waitFor();assert.equal(await page.locator('#delivery a').count(),0);
 });
 for(const [name,stored] of [['missing-owner',null],['expired-local-owner',{...owner,savedAt:Date.now()-86401000}]])await check(name,stored,[],async(page,requests)=>{
  await page.getByText(/ne retrouve pas votre commande/).waitFor();assert.equal(await page.locator('#delivery a').count(),0);assert.equal(requests.length,0);
 });
 console.log(`${passed} synthetic delivery UI regressions passed; live Stripe/IGN validation is separate.`);
}finally{await browser.close()}
