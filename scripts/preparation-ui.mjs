// SYNTHETIC provider/API fixtures for preparation UX, never evidence of real IGN/Stripe.
import assert from 'node:assert/strict';
import {readFile,mkdir} from 'node:fs/promises';
import {chromium} from 'playwright';
import {PNG} from 'pngjs';
const front='https://sitehistory.test',api='https://api.sitehistory.test';
const requested='276440000B0151';
const success={preview_token:'fixture-preview-token-not-a-real-token-0000',summary:'Dossier HTML/PDF prêt — données SYNTHÉTIQUES.',payments_enabled:true};
const checkoutSuccess={order_id:'synthetic-order-0000000000',order_token:'synthetic-owner-token-not-a-real-secret-0000',url:'https://checkout.stripe.com/c/pay/cs_test_synthetic_fixture'};
const pngs=[true,false].map(old=>{const p=new PNG({width:256,height:256});for(let y=0;y<256;y++)for(let x=0;x<256;x++){const n=(x*3+y*7)%180+30,i=(y*256+x)*4;p.data.set(old?[n,n,n,255]:[30,n,200-n/2,255],i)}return PNG.sync.write(p)});
const matrices=Array.from({length:5},(_,i)=>{const z=14+i;return `<TileMatrix><o:Identifier>${z}</o:Identifier><ScaleDenominator>${559082264.0287178/2**z}</ScaleDenominator><TopLeftCorner>-20037508.342789244 20037508.342789244</TopLeftCorner><TileWidth>256</TileWidth><TileHeight>256</TileHeight><MatrixWidth>${2**z}</MatrixWidth><MatrixHeight>${2**z}</MatrixHeight></TileMatrix>`}).join('');
const caps=`<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:o="http://www.opengis.net/ows/1.1"><Contents>${['ORTHOIMAGERY.ORTHOPHOTOS','ORTHOIMAGERY.ORTHOPHOTOS.1950-1965'].map(id=>`<Layer><o:Identifier>${id}</o:Identifier><Style isDefault="true"><o:Identifier>fixture</o:Identifier></Style><Format>image/png</Format><TileMatrixSetLink><TileMatrixSet>PM</TileMatrixSet></TileMatrixSetLink></Layer>`).join('')}<TileMatrixSet><o:Identifier>PM</o:Identifier><o:SupportedCRS>EPSG:3857</o:SupportedCRS>${matrices}</TileMatrixSet></Contents></Capabilities>`;
const parcel=id=>({type:'Feature',properties:{idu:id,nom_com:'Commune SYNTHÉTIQUE',code_insee:'27644',section:'0B',numero:id.slice(-4)},geometry:{type:'Polygon',coordinates:[[[1.5298,49.1498],[1.5302,49.1498],[1.5302,49.1502],[1.5298,49.1502],[1.5298,49.1498]]]}});
const browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{})});
await mkdir('test-results/preparation-ui',{recursive:true});let passed=0;
async function scenario(name,reply,run,{slowCatalogue=false,checkoutReply={status:200,json:checkoutSuccess},blockStorage=false}={}){
 const context=await browser.newContext({viewport:{width:390,height:844}});let requests=0,checkoutRequests=0,releaseCatalogue,releaseCheckout;
 if(blockStorage)await context.addInitScript(()=>{Storage.prototype.setItem=()=>{throw Error('Synthetic blocked storage')}});
 const checkoutGate=new Promise(resolve=>releaseCheckout=resolve);
 const catalogueGate=new Promise(resolve=>releaseCatalogue=resolve);let releaseReport;
 const reportGate=new Promise(resolve=>releaseReport=resolve);
 try{
  await context.route('**/*',async route=>{
   const u=new URL(route.request().url()),cors={'Access-Control-Allow-Origin':front,'Access-Control-Allow-Headers':'Content-Type'};
   if(route.request().method()==='OPTIONS')return route.fulfill({status:204,headers:cors});
   if(u.origin===front){
    if(u.pathname==='/assets/config.js')return route.fulfill({contentType:'text/javascript',body:`window.SITEHISTORY_API=${JSON.stringify(api)}`});
    const file=u.pathname==='/demo.html'?'demo.html':u.pathname.slice(1);return route.fulfill({contentType:file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html',body:await readFile('docs/'+file)});
   }
   if(u.hostname==='unpkg.com')return route.fulfill({contentType:u.pathname.endsWith('.js')?'text/javascript':'text/css',body:await readFile('node_modules/leaflet/dist/'+u.pathname.split('/').pop())});
   if(u.hostname==='data.geopf.fr'){
    if(u.searchParams.get('REQUEST')==='GetCapabilities'){if(slowCatalogue)await catalogueGate;return route.fulfill({contentType:'text/xml',headers:cors,body:caps})}
    if(u.searchParams.get('REQUEST')==='GetTile')return route.fulfill({contentType:'image/png',headers:cors,body:pngs[u.searchParams.get('LAYER').includes('1950')?0:1]});
    return route.fulfill({headers:cors,json:{features:[{type:'Feature',properties:{label:'Adresse SYNTHÉTIQUE'},geometry:{type:'Point',coordinates:[1.53,49.15]}}]}});
   }
   if(u.hostname==='apicarto.ign.fr')return route.fulfill({headers:cors,json:{features:[parcel(u.searchParams.get('numero')==='0151'?requested:'276440000B0150')]}});
   if(u.origin===api&&u.pathname==='/api/previews'){
    requests++;assert.equal(route.request().postDataJSON().parcel_id,requested);assert.equal(route.request().postDataJSON().address,'','Identifier search must not inherit the demo address');await reportGate;
    if(reply==='network')return route.abort('failed');
    return route.fulfill({headers:cors,...reply});
   }
   if(u.origin===api&&u.pathname==='/api/checkout'){
    checkoutRequests++;assert.equal(route.request().postDataJSON().preview_token,success.preview_token);await checkoutGate;
    if(checkoutReply==='network')return route.abort('failed');
    return route.fulfill({headers:cors,...checkoutReply});
   }
   if(u.origin==='https://checkout.stripe.com')return route.fulfill({contentType:'text/html',body:'<h1>Stripe navigation fixture — no actual payment</h1>'});
   throw Error('Unexpected synthetic request: '+u.origin+u.pathname);
  });
  const page=await context.newPage();await page.goto(front+'/demo.html',{waitUntil:'domcontentloaded'});
  await run(page,{releaseCatalogue,releaseReport,releaseCheckout,requests:()=>requests,checkoutRequests:()=>checkoutRequests});
  await page.screenshot({path:`test-results/preparation-ui/${name}.png`,fullPage:true});passed++;console.log('SYNTHETIC preparation passed: '+name);
 }catch(error){
  console.log('::error title=Synthetic preparation/Checkout regression::'+(name+': '+error.message).replaceAll('%','%25').replaceAll('\r','%0D').replaceAll('\n','%0A'));
  const page=context.pages()[0];if(page)await page.screenshot({path:`test-results/preparation-ui/${name}-failure.png`}).catch(()=>{});throw error;
 }finally{releaseCatalogue();releaseReport();releaseCheckout();await context.close()}
}
async function identify(page){
 await page.locator('#identifier').fill(requested);await page.locator('#identifier-form button').click();
 await page.waitForFunction(id=>document.querySelector('#candidates').value===id,requested);
}
async function start(page){
 await page.waitForFunction(()=>document.querySelector('#candidates').options.length>1&&document.querySelector('#comparison-state').dataset.oldHash);
 await identify(page);await page.waitForFunction(()=>document.querySelector('#comparison-state').dataset.oldHash);
 await page.locator('#confirm').click();await page.locator('#prepare').click();
}
try{
 await scenario('visible-wait-and-ready',{status:200,json:success},async(page,c)=>{
  await start(page);await page.waitForFunction(()=>document.querySelector('#report-status').dataset.state==='preparing');
  assert.ok((await page.locator('#report-status').innerText()).includes('Préparation en cours'));
  assert.equal(await page.locator('#prepare').getAttribute('aria-busy'),'true');assert.ok(await page.locator('#prepare').isDisabled());assert.ok(await page.locator('#checkout').isDisabled());
  const box=await page.locator('#report-status').boundingBox();assert.ok(box.y+box.height>0&&box.y<844,'Waiting message outside clicked button viewport');
  await page.locator('#prepare').evaluate(b=>b.click());assert.equal(c.requests(),1,'Double click started a second report');
  await page.waitForFunction(()=>/1 s|2 s/.test(document.querySelector('#report-elapsed').textContent));
  c.releaseReport();await page.waitForFunction(()=>document.querySelector('#report-status').dataset.state==='ready');
  assert.ok(!await page.locator('#checkout').isDisabled());assert.ok(await page.locator('#prepare').isDisabled());assert.ok(await page.locator('#report-elapsed').isHidden());
 });
 for(const [name,reply,expected] of [
  ['quota-429',{status:429,json:{detail:'Limite temporaire atteinte. Réessayez plus tard.'}},'Limite temporaire'],
  ['source-503',{status:503,json:{detail:'Source temporairement indisponible.'}},'Source temporairement'],
  ['gateway-html',{status:502,contentType:'text/html',body:'<h1>Gateway unavailable</h1>'},'HTTP 502'],
  ['network','network','Impossible de joindre'],
  ['incomplete-response',{status:200,json:{}},'Réponse de préparation incomplète']
 ])await scenario(name,reply,async(page,c)=>{
  await start(page);c.releaseReport();await page.waitForFunction(()=>document.querySelector('#report-status').dataset.state==='failed');
  assert.ok((await page.locator('#report-status').innerText()).includes(expected));assert.ok((await page.locator('#report-status').innerText()).includes('Aucun paiement'));
  assert.ok(await page.locator('#checkout').isDisabled());assert.ok(!await page.locator('#prepare').isDisabled());assert.equal(await page.locator('#prepare').innerText(),'Réessayer la préparation');
 });
 await scenario('early-identifier-preserved',{status:200,json:success},async(page,c)=>{
  await identify(page);c.releaseCatalogue();await page.waitForFunction(()=>document.querySelector('#comparison-state').dataset.oldHash);
  // Catalogue completion must not replace the explicitly requested151 by default150.
  await page.waitForTimeout(500);assert.equal(await page.locator('#candidates').inputValue(),requested);
 },{slowCatalogue:true});
 await scenario('cadastral-reference-in-address-input',{status:200,json:success},async(page,c)=>{
  await page.waitForFunction(()=>document.querySelector('#candidates').options.length>1&&document.querySelector('#comparison-state').dataset.oldHash);
  await page.locator('#address').fill(requested);await page.locator('#search').click();
  await page.waitForFunction(id=>document.querySelector('#candidates').value===id&&document.querySelector('#comparison-state').dataset.oldHash,requested);
  assert.equal(await page.locator('#identifier').inputValue(),requested);await page.locator('#confirm').click();await page.locator('#prepare').click();
  c.releaseReport();await page.waitForFunction(()=>document.querySelector('#report-status').dataset.state==='ready');
  assert.equal(c.requests(),1);
 });
 async function prepared(page,c){await start(page);c.releaseReport();await page.waitForFunction(()=>document.querySelector('#report-status').dataset.state==='ready')}
 await scenario('checkout-visible-wait-and-navigation',{status:200,json:success},async(page,c)=>{
  await page.evaluate(()=>window.addEventListener('beforeunload',()=>{const a=document.querySelector('#checkout-link');localStorage.setItem('synthetic-link-proof',JSON.stringify({hidden:a.hidden,href:a.href}))}));
  await prepared(page,c);await page.locator('#checkout').click();
  await page.waitForFunction(()=>document.querySelector('#checkout-status').dataset.state==='opening');
  assert.equal(await page.locator('#checkout').getAttribute('aria-busy'),'true');assert.ok(await page.locator('#checkout').isDisabled());
  const box=await page.locator('#checkout-status').boundingBox();assert.ok(box.y>=0&&box.y+box.height<=844,'Checkout progress outside mobile viewport');
  await page.locator('#checkout').evaluate(b=>b.click());assert.equal(c.checkoutRequests(),1);
  const navigation=page.waitForURL(checkoutSuccess.url);c.releaseCheckout();await navigation;
  const stored=(await contextStorage(page)).find(o=>o.origin===front);assert.ok(stored.localStorage.some(v=>v.name==='sitehistory-order'&&JSON.parse(v.value).id===checkoutSuccess.order_id));
  assert.deepEqual(JSON.parse(stored.localStorage.find(v=>v.name==='synthetic-link-proof').value),{hidden:false,href:checkoutSuccess.url},'A manual link must be present before automatic navigation');
 });
 for(const [name,checkoutReply,expected] of [
  ['checkout-stripe-503',{status:503,json:{detail:'Stripe test indisponible. Réessayez cette même commande.'}},'Stripe test indisponible'],
  ['checkout-quota-429',{status:429,json:{detail:'Limite temporaire atteinte. Réessayez dans environ 5 minute(s).'}},'Limite temporaire'],
  ['checkout-gateway-html',{status:502,contentType:'text/html',body:'<h1>Gateway unavailable</h1>'},'HTTP 502'],
  ['checkout-expired-410',{status:410,json:{detail:'Aperçu expiré ; préparez de nouveau le dossier avant paiement.'}},'Aperçu expiré'],
  ['checkout-incomplete',{status:200,json:{}},'Réponse de paiement TEST incomplète'],
  ['checkout-foreign-url',{status:200,json:{...checkoutSuccess,url:'https://other.example/cs_test_fixture'}},'Réponse de paiement TEST incomplète'],
  ['checkout-live-url',{status:200,json:{...checkoutSuccess,url:'https://checkout.stripe.com/c/pay/cs_live_fixture'}},'Réponse de paiement TEST incomplète'],
  ['checkout-network','network','Impossible de joindre'],
  ['checkout-blocked-storage',{status:200,json:checkoutSuccess},'Le navigateur bloque la conservation']
 ])await scenario(name,{status:200,json:success},async(page,c)=>{
  await prepared(page,c);await page.locator('#checkout').click();c.releaseCheckout();
  await page.waitForFunction(()=>document.querySelector('#checkout-status').dataset.state==='failed');
  assert.ok((await page.locator('#checkout-status').innerText()).includes(expected));assert.equal(page.url(),front+'/demo.html');
  // Chromium rounds scrolling to device pixels; DOM boxes retain fractional pixels.
  const box=await page.locator('#checkout-status').boundingBox();assert.ok(box.y>=-1&&box.y+box.height<=845,'Checkout error outside mobile viewport: '+JSON.stringify(box));
  assert.ok(await page.locator('#checkout-link').isHidden());assert.equal(await page.locator('#checkout').getAttribute('aria-busy'),null);
  if(name==='checkout-expired-410'){assert.ok(await page.locator('#checkout').isDisabled());assert.ok(!await page.locator('#prepare').isDisabled())}
  else{assert.ok(!await page.locator('#checkout').isDisabled());assert.ok(await page.locator('#prepare').isDisabled())}
  if(name==='checkout-stripe-503'){
   await page.locator('#checkout').click();await page.waitForFunction(()=>document.querySelector('#checkout-status').dataset.state==='failed');
   assert.equal(c.requests(),1,'Checkout retry must not generate a second report');assert.equal(c.checkoutRequests(),2);
  }
 },{checkoutReply,blockStorage:name==='checkout-blocked-storage'});
 await scenario('checkout-selection-changed',{status:200,json:success},async(page,c)=>{
  await prepared(page,c);await page.locator('#checkout').click();
  await page.locator('#candidates').selectOption('');c.releaseCheckout();
  await page.waitForFunction(()=>document.querySelector('#checkout-status').dataset.state==='failed');
  assert.ok((await page.locator('#checkout-status').innerText()).includes('La sélection a changé'));assert.ok(await page.locator('#checkout-link').isHidden());assert.equal(page.url(),front+'/demo.html');
 });
 console.log(`${passed} synthetic preparation regressions passed; real parcel preparation remains a separate test.`);
}finally{await browser.close()}
async function contextStorage(page){return (await page.context().storageState()).origins}
