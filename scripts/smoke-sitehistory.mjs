// Live IGN check: success requires distinct raster fingerprints, not just loaded tiles.
import { chromium } from 'playwright';
import { PNG } from 'pngjs';
import { mkdir } from 'node:fs/promises';
const base=process.env.SITEHISTORY_BASE_URL||'https://matthieuangeli-code.github.io/satellite-timeline-viewer';
const output=process.env.SITEHISTORY_SCREENSHOTS||'test-results/sitehistory';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const addresses=['37 rue Grande, 27510 Tilly','1 place de la Comédie, 69001 Lyon','1 place du Bouffay, 44000 Nantes'];
let failures=0;
try {
 for(const mobile of [false,true]) {
  const page=await browser.newPage({viewport:{width:mobile?390:1360,height:mobile?844:1000}});
  try {
   await page.goto(base+'/index.html',{waitUntil:'domcontentloaded'});
   if(!await page.locator('#dossier').isVisible())throw Error('Paid report explanation missing');
   const offer=await page.locator('#dossier').innerText();
   if(!offer.includes('HTML autonome')||!offer.includes('PDF')||!offer.includes('gratuitement'))throw Error('Free exploration / paid export distinction missing');
   if(await page.locator('a[href*="buy.stripe.com"]').count())throw Error('Standalone payment bypasses parcel confirmation');
   if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Homepage overflows viewport');
   await page.screenshot({path:`${output}/homepage-${mobile?'mobile':'desktop'}.png`,fullPage:true});
   await page.locator('.offer a').click();
   await page.locator('#official').waitFor({state:'visible'});
   if(!String(await page.locator('#official').getAttribute('href')).startsWith('https://remonterletemps.ign.fr/'))throw Error('Official IGN link missing');
   console.log(JSON.stringify({name:`homepage-${mobile?'mobile':'desktop'}`,passed:true}));
  } catch(e) {failures++;console.error(JSON.stringify({name:'homepage',mobile,passed:false,error:e.message}));}
  finally {await page.close();}
 }
 for(const mobile of [false,true]) for(const [index,address] of addresses.entries()) {
  const name=`${mobile?'mobile':'desktop'}-${index+1}`;
  const context=await browser.newContext({viewport:{width:mobile?390:1360,height:mobile?844:1000}});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  try {
   const response=await page.goto(base+'/demo.html',{waitUntil:'domcontentloaded',timeout:40000});
   if(response.status()!==200)throw Error('Demo HTTP '+response.status());
   await page.locator('#era').waitFor({state:'visible'});
   await page.waitForFunction(()=>document.querySelector('#comparison-state').dataset.oldHash||document.querySelector('#status').classList.contains('failed'),null,{timeout:150000});
   await page.locator('#address').fill(address);await page.locator('#search').click();
   await page.waitForFunction(()=>document.querySelector('#comparison-state').dataset.oldHash&&document.querySelector('#candidates').options.length>1,null,{timeout:150000});
   const candidate= index===0 ? '276440000B0150' : await page.locator('#candidates option').nth(1).getAttribute('value');
   await page.locator('#candidates').selectOption(candidate);
   await page.locator('#confirm').click();
   const state=await page.locator('#comparison-state').evaluate(e=>({old:e.dataset.oldHash,recent:e.dataset.newHash}));
   if(!state.old||state.old===state.recent)throw Error('Raster images not demonstrably different');
   const sources=await Promise.all(['old-source','new-source'].map(id=>page.locator('#'+id).innerText()));
   if(!sources[0].includes('ORTHOIMAGERY.')||sources[0]===sources[1])throw Error('Distinct IGN sources missing');
   const boxes=await Promise.all(['map-old','map-new'].map(id=>page.locator('#'+id).boundingBox()));
   if(boxes[0].width!==boxes[1].width||boxes[0].height!==boxes[1].height)throw Error('Unequal frame dimensions');
   const images=[];for(const id of ['map-old','map-new'])images.push(PNG.sync.read(await page.locator('#'+id).screenshot({path:`${output}/${name}-${id}.png`})));
   let changed=0,total=0;for(let y=60;y<images[0].height-40;y+=3)for(let x=40;x<images[0].width-30;x+=3){const j=(y*images[0].width+x)*4;let delta=0;for(let k=0;k<3;k++)delta+=Math.abs(images[0].data[j+k]-images[1].data[j+k]);if(delta>36)changed++;total++}
   if(!total||changed/total<.01)throw Error('Visible screenshots insufficiently different');
   if(process.env.SITEHISTORY_PREVIEW_CHECK==='1'&&!mobile&&index===0) {
    if(await page.locator('#prepare').isDisabled())throw Error('Confirmed parcel cannot start report preparation');
    await page.locator('#prepare').click();
    await page.waitForFunction(()=>document.querySelector('#report-status').textContent.includes('Dossier HTML/PDF prêt')||document.querySelector('#status').classList.contains('failed'),null,{timeout:300000});
    if(!(await page.locator('#report-status').innerText()).includes('Dossier HTML/PDF prêt'))throw Error('Browser report preparation failed');
    if(!await page.locator('#checkout').isDisabled())throw Error('Unconfigured Stripe unexpectedly enabled Checkout');
    console.log(JSON.stringify({name:'hosted-browser-report',parcel:'276440000B0150',prepared:true,checkoutEnabled:false}));
   }
   await page.screenshot({path:`${output}/${name}.png`,fullPage:true});
   // Force historical requests to fail in a fresh page: no recent substitute allowed.
   const missing=await context.newPage();
   await missing.route('**/wmts?**',route=>{const u=new URL(route.request().url());if(u.searchParams.get('REQUEST')==='GetTile'&&u.searchParams.get('LAYER')!=='ORTHOIMAGERY.ORTHOPHOTOS')return route.fulfill({status:404,body:'Intentional test outage',headers:{'Access-Control-Allow-Origin':'*'}});return route.continue()});
   await missing.goto(base+'/demo.html',{waitUntil:'domcontentloaded'});
   await missing.waitForFunction(()=>/Aucune période historique vérifiée|Image manquante|Comparaison non validée/.test(document.querySelector('#comparison-state').textContent),null,{timeout:150000});
   if(await missing.locator('#comparison-state').getAttribute('data-old-hash'))throw Error('Missing image incorrectly validated');
   if(!await missing.locator('#prepare').isDisabled())throw Error('Missing image allowed purchase preflight');
   await missing.screenshot({path:`${output}/${name}-missing.png`,fullPage:true});
   if(errors.length)throw Error(errors.join('; '));
   console.log(JSON.stringify({name,address,passed:true,sources,hashes:state,visualDifference:changed/total}));
  }catch(e){failures++;await page.screenshot({path:`${output}/${name}-FAILED.png`,fullPage:true}).catch(()=>{});console.error(JSON.stringify({name,address,passed:false,error:e.message}));}
  finally{await context.close()}
 }
 if(failures)process.exitCode=1;
}finally{await browser.close()}
