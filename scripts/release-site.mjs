// Public release checks: real example rasters, complete navigation and accessible pages.
// Does not create an order, make a payment or read a customer's report.
import assert from 'node:assert/strict';
import {readFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright';
import {PNG} from 'pngjs';

const base=(process.env.SITEHISTORY_BASE_URL||'http://127.0.0.1:8000').replace(/\/$/,'')+'/';
const pages=['index.html','sources.html','confidentialite.html','service.html','404.html'];
const out='test-results/release';await mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});
try{
 const request=await browser.newContext();
 const response=await request.request.get(base+'assets/example-imagery.json');assert.equal(response.status(),200);
 const provenance=await response.json();assert.equal(provenance.images.length,2);
 const [old,recent]=provenance.images;
 assert.notEqual(old.resource,recent.resource);assert.notEqual(old.raw_sha256,recent.raw_sha256);
 assert.notEqual(old.sha256,recent.sha256,'Displayed capture files must differ');
 assert.deepEqual(old.bbox,recent.bbox);assert.equal(old.crs,recent.crs);
 assert.equal(old.width,recent.width);assert.equal(old.height,recent.height);
 for(const image of provenance.images){
  const response=await request.request.get(base+'assets/'+image.file);assert.equal(response.status(),200);
  const data=await response.body();assert.equal(createHash('sha256').update(data).digest('hex'),image.sha256);
 }
 const checked=new Map();
 for(const width of [1360,390,320])for(const name of pages){
  const context=await browser.newContext({viewport:{width,height:900},isMobile:width<600,hasTouch:width<600});
  const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
  assert.equal((await page.goto(base+name,{waitUntil:'load'})).status(),200);
  await page.evaluate(()=>document.fonts.ready);
  assert.equal(await page.evaluate(()=>innerWidth),width);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow: '+name+'/'+width);
  assert.equal(await page.locator('h1').count(),1);
  const links=await page.locator('a[href]').evaluateAll(nodes=>nodes.map(node=>node.href));
  for(const link of links){
   const url=new URL(link);if(!url.href.startsWith(base)||url.pathname.endsWith('/demo.html'))continue;
   const withoutHash=url.href.split('#')[0];
   if(!checked.has(withoutHash)){
    const response=await context.request.get(withoutHash);assert.equal(response.status(),200,'Broken internal link: '+withoutHash);
    checked.set(withoutHash,true);
   }
   if(url.hash&&url.pathname===new URL(base+name).pathname){
    assert.equal(await page.locator('[id]').evaluateAll((nodes,id)=>nodes.filter(node=>node.id===id).length,decodeURIComponent(url.hash.slice(1))),1,'Broken anchor: '+link);
   }
  }
  if(name==='index.html'){
   assert.equal(await page.locator('script:not([type="application/ld+json"])').count(),0,'Fictional comparison script left on homepage');
   assert.equal(await page.locator('#exemple-ign img').count(),2);
   const images=await page.locator('#exemple-ign img').evaluateAll(nodes=>nodes.map(node=>({loaded:node.complete&&node.naturalWidth>0,width:node.naturalWidth,height:node.naturalHeight})));
   assert.ok(images.every(image=>image.loaded&&image.width===720&&image.height===720));
   const rasters=[];
   for(const image of await page.locator('#exemple-ign img').all())rasters.push(PNG.sync.read(await image.screenshot()));
   let changed=0,total=0;
   for(let y=.1;y<.9;y+=.03)for(let x=.1;x<.9;x+=.03){
    const pixels=rasters.map(image=>4*(Math.floor(y*image.height)*image.width+Math.floor(x*image.width)));
    const delta=[0,1,2].reduce((sum,c)=>sum+Math.abs(rasters[0].data[pixels[0]+c]-rasters[1].data[pixels[1]+c]),0);
    if(delta>36)changed++;total++;
   }
   assert.ok(changed/total>.01,'Visible example images are insufficiently different');
   await page.locator('.hero').screenshot({path:`${out}/hero-${width}.png`});
   assert.equal(await page.locator('a[href*="buy.stripe.com"]').count(),0);
   assert.ok((await page.locator('.release-note').innerText()).includes('ventes réelles ne sont pas ouvertes'));
   const copy=await page.locator('body').innerText();
   assert.ok(!copy.includes('4,90')&&!copy.includes('4242 4242')&&!copy.includes('paiement fictif'),'Technical sandbox instructions leaked into commercial presentation');
   const target=await page.locator('.offer--paid a').getAttribute('href');
   assert.equal(new URL(target,base).href,base+'demo.html');
   assert.equal((await context.request.get(new URL(target,base).href)).status(),200);
  }
  // WCAG checks run on actual rendered content, including contrast and names.
  await page.addScriptTag({content:await readFile(new URL('../node_modules/axe-core/axe.min.js',import.meta.url),'utf8')});
  const result=await page.evaluate(async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}}));
  assert.deepEqual(result.violations.map(v=>({id:v.id,impact:v.impact,elements:v.nodes.map(n=>n.target)})),[],'Accessibility violations: '+name+'/'+width);
  assert.deepEqual(errors,[]);
  if(name==='index.html'||name==='service.html')await page.screenshot({path:`${out}/${name.replace('.html','')}-${width}.png`,fullPage:true});
  console.log(JSON.stringify({page:name,width,passed:true}));await context.close();
 }
 await request.close();
 console.log('Public release verified: accessible pages, working internal navigation, actual distinct IGN captures and closed real sales.');
}finally{await browser.close()}
