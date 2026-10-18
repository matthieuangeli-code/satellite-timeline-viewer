// Real hosted Checkout navigation only: never enter a card or submit payment.
import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
const front='https://matthieuangeli-code.github.io/satellite-timeline-viewer';
const api='https://sitehistory-api-pilot.onrender.com';
const parcel=process.env.SITEHISTORY_PARCEL_ID||'276440000B0151';
assert.match(parcel,/^[0-9A-Z]{14}$/);
const out='test-results/checkout';await mkdir(out,{recursive:true});
const result={state:'running',parcel,mode:'sandbox-navigation-only',checks:[]};
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const context=await browser.newContext({viewport:{width:1360,height:1000}});
const page=await context.newPage();let preview,order,stage='identify';
// Publish only explicit safe fields. Owner tokens, URLs and report bytes stay in memory.
const detail=d=>typeof d?.detail==='string'?d.detail.replace(/https?:\/\/\S+|(?:sk|rk|cs)_test_\S+/g,'[redacted]').slice(0,300):undefined;
try{
 await page.route(api+'/api/previews',async route=>{
  const r=await route.fetch({timeout:300000});const data=await r.json().catch(()=>null);
  result.previewHttpStatus=r.status();result.previewFailure=detail(data);result.retryAfter=r.headers()['retry-after'];
  if(r.ok())preview=data;
  await route.fulfill({response:r});
 });
 await page.route(api+'/api/checkout',async route=>{
  const r=await route.fetch({timeout:90000});const data=await r.json().catch(()=>null);
  result.checkoutHttpStatus=r.status();result.checkoutFailure=detail(data);
  if(r.ok())order=data;
  await route.fulfill({response:r});
 });
 await page.goto(front+'/demo.html',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('#comparison-state').dataset.oldHash,null,{timeout:180000});
 await page.locator('#identifier').fill(parcel);await page.locator('#identifier-form button').click();
 await page.waitForFunction(id=>document.querySelector('#candidates').value===id&&document.querySelector('#comparison-state').dataset.oldHash,parcel,{timeout:180000});
 await page.locator('#confirm').click();stage='prepare';await page.locator('#prepare').click();
 await page.waitForFunction(()=>['ready','failed'].includes(document.querySelector('#report-status').dataset.state),null,{timeout:300000});
 assert.ok(preview?.preview_token,'Preparation did not succeed; inspect the sanitized HTTP status');
 assert.equal(preview.payments_enabled,true);result.checks.push('real_151_report_prepared');
 stage='checkout';await page.locator('#checkout').click();
 await page.waitForURL('https://checkout.stripe.com/**',{timeout:90000});
 assert.ok(order?.url?.includes('/cs_test_'),'Not a test Checkout session');
 await page.getByText(/4[,.]90/).first().waitFor({timeout:60000});
 assert.equal(new URL(page.url()).hostname,'checkout.stripe.com');result.checks.push('real_browser_reached_stripe_test_490');
 const retry=await context.request.post(api+'/api/checkout',{data:{preview_token:preview.preview_token}});
 assert.equal(retry.status(),200);const again=await retry.json();assert.equal(again.order_id,order.order_id);assert.equal(again.url,order.url);
 result.checks.push('same_prepared_report_reuses_same_checkout');
 await page.screenshot({path:out+'/stripe-test-checkout.png'});result.state='passed';
}catch(e){
 result.state='failed';result.stage=stage;
 // Playwright errors may contain the complete private Checkout URL: omit them.
 result.error=stage==='checkout'?'Checkout navigation or price assertion failed':stage==='prepare'?'Report preparation failed':'Parcel or imagery verification failed';
 if(new URL(page.url()).hostname===new URL(front).hostname){
  result.visibleReportStatus=await page.locator('#report-status').innerText().catch(()=>null);
  result.visibleGlobalStatus=await page.locator('#status').innerText().catch(()=>null);
  await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});
 }
 process.exitCode=1;
}finally{
 await browser.close();await writeFile(out+'/result.json',JSON.stringify(result,null,2));
 console.log('::notice title=SiteHistory Checkout navigation::'+JSON.stringify(result));
}
