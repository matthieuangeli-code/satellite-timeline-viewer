// Public deployment verification. No provider credentials or report tokens are logged.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const base='https://sitehistory-api-pilot.onrender.com';
const origin='https://matthieuangeli-code.github.io';
const output='test-results/backend';
const parcelId=process.env.SITEHISTORY_PARCEL_ID||'276440000B0150';
assert.match(parcelId,/^(?:[0-9]{5}|2[AB][0-9]{3})[0-9]{3}[A-Z0-9]{2}[0-9]{4}$/);
await mkdir(output,{recursive:true});
async function request(path,body,timeout=30000) {
 const response=await fetch(base+path,{method:body?'POST':'GET',headers:{Origin:origin,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(timeout)});
 const data=await response.json().catch(()=>null);
 return {response,data};
}
const result={base,checkedAt:new Date().toISOString(),backend:'unverified',report:{state:'not_run'},delivery:{state:'not_configured'}};
try {
 let health;
 for(let attempt=0;attempt<30;attempt++) {
  try {const r=await request('/api/health',null,15000);if(r.response.ok){health=r.data;break;}} catch {}
  if(attempt<29)await new Promise(resolve=>setTimeout(resolve,10000));
 }
 assert.equal(health?.status,'ok','Backend failed to start within the verification window');
 assert.equal(health.mode,'sandbox');assert.equal(health.storage,'postgresql');
 assert.equal(typeof health.payments_enabled,'boolean');
 result.paymentsEnabled=health.payments_enabled;
 result.delivery={state:health.payments_enabled?'not_verified':'not_configured'};
 const ready=await request('/api/ready');assert.equal(ready.response.status,200);assert.equal(ready.data.storage,'postgresql');
 assert.equal(ready.response.headers.get('access-control-allow-origin'),origin,'GitHub Pages CORS missing');
 const address=await request('/api/addresses?q='+encodeURIComponent('37 rue Grande, 27510 Tilly'));
 assert.equal(address.response.status,200);assert.ok(address.data.features?.length,'Live address search failed');
 const parcel=await request('/api/parcels?identifier='+parcelId);
 assert.equal(parcel.response.status,200);assert.equal(parcel.data.confirmation_required,true);
 assert.equal(parcel.data.features.length,1);assert.ok(parcel.data.features[0].geometry?.coordinates);
 assert.equal(parcel.data.features[0].properties.idu,parcelId,'Exact requested cadastral parcel missing');
 assert.equal((await request('/api/parcels?identifier=invalid')).response.status,422);
 assert.equal((await request('/api/orders/unauthorized-order')).response.status,404);
 assert.equal((await request('/api/orders/unauthorized-order/download/pdf?expires=0&signature=invalid')).response.status,403);
 assert.equal((await request('/api/previews',{parcel_id:'276440000B0150',confirmed:false})).response.status,422);
 assert.equal((await request('/api/checkout',{preview_token:'a'.repeat(43)})).response.status,health.payments_enabled?410:503);
 assert.equal((await request('/api/stripe/webhook',{})).response.status,health.payments_enabled?400:503);
 result.backend='passed';
 console.log('Hosted PostgreSQL, address/cadastre, CORS, confirmation, access and sandbox boundaries passed');
 // Expensive generation is supervised, not repeated for every PR update against the public pilot.
 if(process.env.SITEHISTORY_VERIFY_REPORT==='0') {
  result.report={state:'not_requested'};
  result.delivery={state:health.payments_enabled?'not_verified':'not_configured'};
 } else {
 // A real generation attempt; an upstream outage is recorded as blocked, never as a generated report.
 const preview=await request('/api/previews',{parcel_id:parcelId,confirmed:true,address:parcelId==='276440000B0150'?'37 rue Grande, 27510 Tilly':'',historical_resource:'ORTHOIMAGERY.ORTHOPHOTOS.1950-1965'},300000);
 if(preview.response.status===200) {
  assert.ok(preview.data.preview_token);assert.equal(preview.data.payments_enabled,health.payments_enabled);
  result.report={state:'prepared',summary:preview.data.summary};
  // Token stays in memory. Neither it nor the private report is exported to CI artifacts.
  if(!health.payments_enabled)assert.equal((await request('/api/checkout',{preview_token:preview.data.preview_token})).response.status,503);
 } else {
  result.report={state:'blocked',parcel:parcelId,httpStatus:preview.response.status,reason:preview.data?.detail,retryAfter:preview.response.headers.get('retry-after')};
  assert.equal(preview.response.status,503,'Unexpected generation failure');
  assert.equal(typeof preview.data?.detail,'string');
 }
 }
 console.log(JSON.stringify(result));
} catch(error) {
 result.error=error.message;console.error('Hosted verification failed:',error.message);process.exitCode=1;
} finally {
 await writeFile(output+'/result.json',JSON.stringify(result,null,2));
 const summary=JSON.stringify(result).replaceAll('%','%25').replaceAll('\r','%0D').replaceAll('\n','%0A');
 console.log('::notice title=SiteHistory hosted verification::'+summary);
}
