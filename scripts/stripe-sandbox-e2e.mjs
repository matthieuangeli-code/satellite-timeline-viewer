// Supervised real sandbox payment. Provider credentials stay on Render.
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { mkdir,writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
const api='https://sitehistory-api-pilot.onrender.com',front='https://matthieuangeli-code.github.io/satellite-timeline-viewer';
const out='test-results/stripe-sandbox';await mkdir(out,{recursive:true});
const result={mode:'sandbox',state:'running',checks:[],startedAt:new Date().toISOString()};
const parcelId=process.env.SITEHISTORY_PARCEL_ID||'276440000B0151';assert.match(parcelId,/^\d{5}[A-Z0-9]{9}$/);
const testEmail='sitehistory-sandbox-'+Date.now()+'@example.com';
const protectedValues=new Set();let stage='health',page,browser,context,order,preview,checkId;
const protect=v=>{if(v)protectedValues.add(v);return v};
function safe(value){let text=String(value);for(const v of protectedValues)text=text.replaceAll(v,'[REDACTED]');return text.replace(/https?:\/\/[^\s]+/g,'[URL]').split('\n')[0].slice(0,400);}
function note(name){result.checks.push(name);console.log('Verified: '+name);}
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
async function request(path,{body,token}={}){
 const r=await context.request.fetch(api+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:'Bearer '+token}:{})},data:body?JSON.stringify(body):undefined,timeout:300000});
 return {status:r.status(),data:await r.json().catch(()=>null),response:r};
}
async function github(path,method='GET',body){
 const r=await fetch('https://api.github.com/repos/'+process.env.GITHUB_REPOSITORY+path,{method,headers:{Authorization:'Bearer '+process.env.GITHUB_TOKEN,Accept:'application/vnd.github+json','Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 assert.ok(r.ok,'GitHub restart coordination failed');return r.json();
}
async function input(selectors,value,required=true){
 for(let attempt=0;attempt<(required?40:1);attempt++){
  for(const frame of page.frames()){
   const field=frame.locator(selectors).first();
   if(await field.isVisible().catch(()=>false)&&await field.isEditable().catch(()=>false)){await field.fill(value);return true;}
  }
  if(required)await pause(500);
 }
 if(required)throw Error('Required Checkout input missing: '+selectors);
 return false;
}
async function card(number){
 await input('input[name="email"],input[type="email"]',testEmail);
 const hasCard=async()=>{for(const frame of page.frames())if(await frame.locator('input[name="cardNumber"],input[autocomplete="cc-number"]').first().isVisible().catch(()=>false))return true;return false;};
 if(!await hasCard()){
  const next=page.getByRole('button',{name:/^Continue$|^Continuer$|^Fortsett$/i}).first();
  if(await next.isVisible().catch(()=>false)){await next.click();await pause(1000);}
  const guest=page.getByText(/pay without link|continue without link|continue as guest|payer sans link/i).first();
  if(await guest.isVisible().catch(()=>false)){await guest.click();await pause(1000);}
 }
 await input('input[name="cardNumber"],input[autocomplete="cc-number"]',number);
 await input('input[name="cardExpiry"],input[autocomplete="cc-exp"]','12/30');
 await input('input[name="cardCvc"],input[autocomplete="cc-csc"]','123');
 await input('input[name="billingName"],input[autocomplete="cc-name"]','SiteHistory Sandbox',false);
 for(const frame of page.frames()){
  const country=frame.locator('select[name="billingCountry"],select[autocomplete="country"]').first();
  if(await country.isVisible().catch(()=>false))await country.selectOption('FR');
 }
 await input('input[name="billingPostalCode"],input[autocomplete="postal-code"]','75001',false);
}
async function submit(){
 const button=page.locator('button[type="submit"]').filter({hasText:/Pay|Payer|Betal/}).last();
 await button.click();
}
async function downloadBytes(paths){
 const files={};for(const format of ['html','pdf']){
  const r=await context.request.get(api+paths[format]);assert.equal(r.status(),200,'Signed '+format+' download failed');files[format]=await r.body();
 }return files;
}
async function browserDownloads(){
 const files={};for(const format of ['html','pdf']){
  const event=page.waitForEvent('download');
  await page.getByRole('link',{name:'Télécharger '+format.toUpperCase(),exact:true}).click();
  const download=await event;assert.equal(await download.failure(),null,'Browser download failed');
  const stream=await download.createReadStream();const chunks=[];for await(const chunk of stream)chunks.push(chunk);
  files[format]=Buffer.concat(chunks);
 }return files;
}
try {
 browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 context=await browser.newContext({viewport:{width:1360,height:1000}});page=await context.newPage();
 const health=await request('/api/health');assert.equal(health.data.mode,'sandbox');assert.equal(health.data.payments_enabled,true,'Stripe test not enabled');assert.ok(health.data.instance,'Restart marker missing');
 note('sandbox_enabled');
 stage='confirmed_parcel';
 // Buffer the real response before navigation; the browser can otherwise discard
 // the fetch body before an asynchronous response listener reads it.
 await page.route(api+'/api/checkout',async route=>{
  const response=await route.fetch();const data=await response.json();result.checkoutHttpStatus=response.status();
  if(response.ok()){order=data;protect(order.order_token);protect(order.url);}else result.checkoutFailure=safe(data.detail);
  await route.fulfill({response});
 });
 await page.route(api+'/api/previews',async route=>{
  // Capture the genuine POST response before allowing the UI to report ready.
  // An asynchronous response listener can finish after the next assertion.
  const response=await route.fetch({timeout:300000});const data=await response.json();result.previewHttpStatus=response.status();
  if(response.ok()){preview=data;protect(preview.preview_token);}else result.previewFailure=safe(data.detail);
  await route.fulfill({response});
 });
 await page.goto(front+'/demo.html',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('#comparison-state').dataset.oldHash&&document.querySelector('#candidates').options.length>1,null,{timeout:180000});
 await page.locator('#identifier').fill(parcelId);await page.locator('#identifier-form button').click();
 await page.waitForFunction(id=>document.querySelector('#candidates').value===id&&document.querySelector('#comparison-state').dataset.oldHash,parcelId,{timeout:180000});
 await page.locator('#confirm').click();
 stage='report_preparation';await page.locator('#prepare').click();
 await page.waitForFunction(()=>document.querySelector('#report-status').textContent.includes('Dossier HTML/PDF prêt')||document.querySelector('#status').classList.contains('failed'),null,{timeout:300000});
 assert.ok(preview?.preview_token,'Real report preparation failed');assert.equal(preview.payments_enabled,true);note('confirmed_parcel_and_real_report');
 stage='checkout_creation';await page.locator('#checkout').click();
 await page.waitForURL('https://checkout.stripe.com/**',{timeout:90000});
 assert.ok(order?.url?.includes('/cs_test_'),'Only cs_test Checkout sessions may be submitted');
 const again=await request('/api/checkout',{body:{preview_token:preview.preview_token}});assert.equal(again.status,200);assert.equal(again.data.order_id,order.order_id);assert.equal(again.data.url,order.url);note('checkout_idempotent');
 let state=await request('/api/orders/'+order.order_id,{token:order.order_token});assert.equal(state.data.status,'pending');assert.deepEqual(state.data.downloads,{});
 assert.equal((await request('/api/orders/'+order.order_id,{token:'wrong-owner-token'})).status,404);note('unpaid_and_cross_owner_access_blocked');
 stage='cancelled_return';
 await page.goto(front+'/demo.html?checkout=cancelled',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>!document.querySelector('#order-panel').hidden,null,{timeout:30000});
 assert.equal(await page.locator('#delivery a').count(),0);note('abandoned_return_has_no_downloads');
 stage='forged_success_return';
 await page.goto(front+'/demo.html?checkout=returned',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>!document.querySelector('#order-panel').hidden,null,{timeout:30000});
 assert.equal(await page.locator('#delivery a').count(),0);note('success_redirect_is_not_payment_proof');
 stage='declined_test_card';await page.goto(order.url,{waitUntil:'domcontentloaded'});
 await card('4000000000000002');await submit();
 await page.getByText(/your (?:credit )?card was declined|carte a été refusée|carte est refusée/i).first().waitFor({timeout:60000});
 state=await request('/api/orders/'+order.order_id,{token:order.order_token});assert.equal(state.data.status,'pending');assert.deepEqual(state.data.downloads,{});note('declined_payment_has_no_downloads');
 await page.screenshot({path:out+'/declined-test-card.png'});
 stage='successful_test_card';await card('4242424242424242');await submit();
 await page.waitForURL(front+'/demo.html?checkout=returned',{timeout:120000});
 for(let i=0;i<30;i++){
  state=await request('/api/orders/'+order.order_id,{token:order.order_token});
  if(state.data.status==='ready')break;await pause(3000);
 }
 assert.equal(state.data.status,'ready','Signed webhook did not unlock delivery');assert.equal(state.data.parcel_id,parcelId);
 await page.locator('#delivery a').first().waitFor({state:'visible',timeout:30000});
 // Wait for maps/search as well: delivery must survive their initial invalidation.
 await page.waitForFunction(()=>document.querySelector('#candidates').options.length>1,null,{timeout:120000});
 assert.equal(await page.locator('#delivery a').count(),2);note('real_test_payment_and_signed_webhook_delivery');
 stage='downloads';const signed=state.data.downloads;for(const path of Object.values(signed))protect(path);
 const files=await browserDownloads();assert.ok(files.pdf.subarray(0,5).toString()==='%PDF-');
 const html=files.html.toString();assert.ok(html.includes(parcelId));assert.ok((html.match(/data-evidence-id=/g)||[]).length>=2);
 assert.ok(html.includes('Votre parcelle en bref')&&html.includes('id="environs"')&&html.includes('Fiches des enregistrements retournés'),'Enriched report sections missing from the actual paid download');
 const text=spawnSync('pdftotext',['-','-'],{input:files.pdf,maxBuffer:3000000});assert.equal(text.status,0,'PDF could not be read');assert.ok(text.stdout.toString().includes(parcelId));
 assert.ok(text.stdout.toString().includes('Indicateurs environnementaux'));
 assert.ok(text.stdout.toString().includes('Votre parcelle en bref')&&text.stdout.toString().includes('Fiches des enregistrements'),'PDF does not contain the enriched report');
 const reportPage=await context.newPage();
 await reportPage.route('**/*',route=>route.abort());await reportPage.setContent(html,{waitUntil:'load'});
 const historicalCount=await reportPage.locator('.history-thumb').count();
 assert.ok(historicalCount>=1&&historicalCount<=5);
 assert.equal(await reportPage.locator('figure[data-historical="true"]').count(),historicalCount);
 assert.equal(await reportPage.locator('#intro-historique').getAttribute('data-historical-count'),String(historicalCount));
 assert.equal(await reportPage.locator('[data-map-background="ign-current"]').count(),1,'Actual IGN current context background missing');
 const markerCount=await reportPage.locator('.map-marker').count();
 if(markerCount){
  const marker=reportPage.locator('.map-marker').first();const target=await marker.getAttribute('href');await marker.click();
  assert.equal(await reportPage.evaluate(()=>location.hash),target);assert.ok((await reportPage.locator(target).boundingBox()).y>=-1);
 }
 await reportPage.setViewportSize({width:390,height:844});
 assert.ok(await reportPage.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await reportPage.locator('.history-thumb').first().click();
 assert.ok((await reportPage.evaluate(()=>location.hash)).startsWith('#photo-'));
 if(markerCount){const marker=reportPage.locator('.map-marker').first();const target=await marker.getAttribute('href');await marker.click();assert.equal(await reportPage.evaluate(()=>location.hash),target);}
 const planningRecords=await reportPage.locator('#urbanisme .planning-record').count();
 assert.ok(planningRecords>0,'No actual planning records in the delivered Tilly report');
 assert.ok((await reportPage.locator('#erp').innerText()).includes('ERP réglementaire non délivré'));
 assert.ok((await reportPage.locator('#urbanisme').innerText()).includes('ne sont pas annexées intégralement'));
 await reportPage.close();
 assert.ok(text.stdout.toString().includes('Votre terrain à travers les archives aériennes'));
 assert.ok(text.stdout.toString().includes('Documents d’urbanisme et servitudes')&&text.stdout.toString().includes('ERP réglementaire non délivré'));
 result.reportFeatures={planningRecords,planningDocuments:true,officialERPDelivered:false,summary:true,neighbourhoodMap:true,currentIGNBackground:true,detailedRecords:true,historicalIntroCount:historicalCount,verifiedImageryCount:(html.match(/data-evidence-id=/g)||[]).length,clickableMarkers:markerCount?true:'not_applicable_no_geolocated_records',geolocatedMarkers:markerCount};note('enriched_html_and_pdf_contents_verified');
 assert.equal((await context.request.get(api+signed.pdf.replace('signature=','signature=x'))).status(),403);
 const expired=new URL(api+signed.pdf);expired.searchParams.set('expires','0');assert.equal((await context.request.get(expired.toString())).status(),403);
 result.files={htmlBytes:files.html.length,pdfBytes:files.pdf.length,htmlSha256:hash(files.html),pdfSha256:hash(files.pdf)};note('standalone_html_and_readable_pdf_downloaded');note('invalid_and_expired_signed_urls_rejected');
 stage='mobile_delivery';await page.setViewportSize({width:390,height:844});await page.reload({waitUntil:'domcontentloaded'});
 await page.locator('#delivery a').first().waitFor({state:'visible',timeout:30000});
 await page.waitForFunction(()=>document.querySelector('#candidates').options.length>1,null,{timeout:120000});
 assert.equal(await page.locator('#delivery a').count(),2);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.locator('#order-panel').screenshot({path:out+'/mobile-delivery.png'});note('mobile_delivery_survives_reload');
 stage='delivery_recovery_in_new_tab';
 const originalPage=page;page=await context.newPage();await page.setViewportSize({width:390,height:844});
 await page.goto(front+'/demo.html?checkout=returned',{waitUntil:'domcontentloaded'});
 await page.locator('#delivery a').first().waitFor({state:'visible',timeout:30000});
 assert.equal(await page.evaluate(()=>sessionStorage.getItem('sitehistory-order')),null,'Recovery must not depend on the payment tab session');
 assert.equal(await page.locator('#delivery a').count(),2);
 const box=await page.locator('#delivery').boundingBox();assert.ok(box.y>=0&&box.y+box.height<=844,'Downloads are outside the mobile viewport');
 // An old href must be renewed using the owner token before browser download.
 await page.getByRole('link',{name:'Télécharger PDF',exact:true}).evaluate(a=>{const u=new URL(a.href);u.searchParams.set('expires','0');a.href=u.toString()});
 const recovered=await browserDownloads();assert.equal(hash(recovered.html),hash(files.html));assert.equal(hash(recovered.pdf),hash(files.pdf));
 await page.locator('#order-panel').screenshot({path:out+'/new-tab-delivery.png'});await originalPage.close();
 note('new_tab_recovers_same_paid_report');note('stale_download_link_renewed_without_new_payment');
 stage='restart_coordination';
 const before=(await request('/api/health')).data.instance;
 const check=await github('/check-runs','POST',{name:'SiteHistory sandbox persistence',head_sha:process.env.GITHUB_SHA,status:'in_progress',output:{title:'Waiting for Render restart',summary:'Test payment and downloads succeeded. Operator may restart the dedicated free service; no credential or order token is exposed.'}});checkId=check.id;
 let restarted=false;
 for(let i=0;i<48;i++){
  try{const now=await request('/api/health');if(now.status===200&&now.data.instance!==before&&now.data.payments_enabled===true){restarted=true;break;}}catch{}
  await pause(5000);
 }
 assert.ok(restarted,'Process restart was not observed');
 stage='persistent_downloads';
 state=await request('/api/orders/'+order.order_id,{token:order.order_token});assert.equal(state.data.status,'ready');
 const restored=await downloadBytes(signed);assert.equal(hash(restored.html),hash(files.html));assert.equal(hash(restored.pdf),hash(files.pdf));note('same_paid_report_survives_actual_restart');
 result.state='passed';
 await github('/check-runs/'+checkId,'PATCH',{status:'completed',conclusion:'success',output:{title:'Report persistence verified',summary:'A different server process served the same paid report and matching HTML/PDF hashes using the original signed URLs.'}});
} catch(error){
 result.state='failed';result.stage=stage;result.error=safe(error.message);process.exitCode=1;
 if(page){
  result.controls=await page.locator('input,select,button').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().width).map(n=>({tag:n.tagName,name:n.name,type:n.type,id:n.id,text:n.tagName==='BUTTON'?n.innerText.slice(0,100):undefined}))).catch(()=>[]);
  result.alerts=await page.locator('[role="alert"],.FieldError,.PaymentMethodForm-error').allTextContents().catch(()=>[]);
  if(page.url().startsWith('https://checkout.stripe.com/')){
   result.screenText=(await page.locator('body').innerText().catch(()=>'')).slice(0,2500).replaceAll(testEmail,'[test email]').replace(/https?:\/\/[^\s]+/g,'[URL]').replace(/cs_test_[a-zA-Z0-9_-]+/g,'[test session]');
  }
  await page.screenshot({path:out+'/failure.png'}).catch(()=>{});
 }
 if(checkId)await github('/check-runs/'+checkId,'PATCH',{status:'completed',conclusion:'failure',output:{title:'Persistence check failed',summary:safe(error.message)}}).catch(()=>{});
} finally {
 result.finishedAt=new Date().toISOString();await writeFile(out+'/result.json',JSON.stringify(result,null,2));
 const summary=JSON.stringify(result).replaceAll('%','%25').replaceAll('\r','%0D').replaceAll('\n','%0A');
 console.log('::notice title=SiteHistory sandbox payment::'+summary);await browser?.close();
}
