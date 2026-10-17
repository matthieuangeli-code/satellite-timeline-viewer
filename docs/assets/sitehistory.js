/* Public-only exploration: no credentials, invented layers or fallback imagery. */
(async function () {
'use strict';
const $=id=>document.getElementById(id), api=(window.SITEHISTORY_API||'').replace(/\/$/,'');
const WMTS='https://data.geopf.fr/wmts', CARTO='https://apicarto.ign.fr/api/cadastre/parcelle';
let layers=[], candidates=[], selected=null, confirmed=false, generation=0, selectionGeneration=0, prepared=null;
let epoch=0, rendering=0, maps=[], raster=[null,null], outlines=[null,null], validPair=false, debounce;
const status=(t,failed=false)=>{$('status').textContent=t;$('status').classList.toggle('failed',failed)};
const json=async url=>{const r=await fetch(url,{signal:AbortSignal.timeout(30000)});if(!r.ok)throw Error('Service indisponible (HTTP '+r.status+')');return r.json()};
const idOf=f=>f.properties?.idu||f.properties?.id||f.id||'';
const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n};
const post=async(path,body)=>{const r=await fetch(api+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(240000)});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Opération indisponible');return d};
function invalidate(){confirmed=false;prepared=null;$('confirm').disabled=!selected;$('prepare').disabled=true;$('checkout').disabled=true;$('delivery').replaceChildren();$('report-status').textContent='Confirmez une parcelle avant de préparer un dossier.'}
function matrixXML(root,tag){return [...root.getElementsByTagNameNS('*',tag)]}
function text(root,tag){return matrixXML(root,tag)[0]?.textContent?.trim()||''}
async function catalogue(){
 const r=await fetch(WMTS+'?SERVICE=WMTS&REQUEST=GetCapabilities',{signal:AbortSignal.timeout(120000)});if(!r.ok)throw Error('Catalogue IGN indisponible');
 const xml=new DOMParser().parseFromString(await r.text(),'text/xml');if(matrixXML(xml,'parsererror').length)throw Error('Catalogue IGN illisible');
 const sets={};
 for(const set of matrixXML(xml,'Contents')[0]?.children||[]){
  if(set.localName!=='TileMatrixSet'||!text(set,'SupportedCRS').includes('3857'))continue;
  const matrices={};for(const m of matrixXML(set,'TileMatrix')){
   const scale=Number(text(m,'ScaleDenominator')),z=Math.round(Math.log2(559082264.0287178/scale));
   const origin=text(m,'TopLeftCorner').split(/\s+/).map(Number);
   if(text(m,'TileWidth')!=='256'||text(m,'TileHeight')!=='256'||Math.abs(origin[0]+20037508.342789244)>1||Math.abs(origin[1]-20037508.342789244)>1||Math.abs(scale-559082264.0287178/2**z)/scale>.001)continue;
   matrices[z]={id:text(m,'Identifier'),width:Number(text(m,'MatrixWidth')),height:Number(text(m,'MatrixHeight'))};
  }sets[text(set,'Identifier')]=matrices;
 }
 const result=[];
 for(const l of matrixXML(xml,'Layer')){
  const id=text(l,'Identifier');if(!/^ORTHOIMAGERY\.ORTHOPHOTOS(?:\.?\d{4}(?:-\d{4})?)?$/.test(id))continue;
  const current=id==='ORTHOIMAGERY.ORTHOPHOTOS',years=id.match(/\d{4}(?:-\d{4})?/);
  const styles=matrixXML(l,'Style'),style=styles.find(s=>s.getAttribute('isDefault')==='true')||styles[0];
  const format=matrixXML(l,'Format').map(n=>n.textContent).find(s=>s==='image/jpeg'||s==='image/png');
  if(!style||!format)continue;
  for(const link of matrixXML(l,'TileMatrixSetLink')){
   const set=text(link,'TileMatrixSet');let matrices=structuredClone(sets[set]||{});
   const limits=matrixXML(link,'TileMatrixLimits');if(limits.length){
    for(const z of Object.keys(matrices)){const limit=limits.find(n=>text(n,'TileMatrix')===matrices[z].id);if(!limit)delete matrices[z];else matrices[z].limits=Object.fromEntries(['MinTileRow','MaxTileRow','MinTileCol','MaxTileCol'].map(k=>[k,Number(text(limit,k))]));}
   }
   const zooms=Object.keys(matrices).map(Number);if(!zooms.length)continue;
   const bb=matrixXML(l,'WGS84BoundingBox')[0];
   result.push({id,style:text(style,'Identifier'),format,set,matrices,min:Math.min(...zooms),max:Math.min(18,Math.max(...zooms)),period:current?'Mosaïque récente (date locale variable)':years[0].replace('-','–'),current,bbox:bb?[...text(bb,'LowerCorner').split(/\s+/),...text(bb,'UpperCorner').split(/\s+/)].map(Number):null});break;
  }
 }
 if(!result.some(l=>l.current))throw Error('La couche récente n’est pas décrite par IGN.');return result;
}
function tileURL(l,c){const m=l.matrices[c.z];if(!m)return '';const lim=m.limits||{};if(c.x<(lim.MinTileCol??0)||c.x>(lim.MaxTileCol??m.width-1)||c.y<(lim.MinTileRow??0)||c.y>(lim.MaxTileRow??m.height-1))return '';return WMTS+'?'+new URLSearchParams({SERVICE:'WMTS',VERSION:'1.0.0',REQUEST:'GetTile',LAYER:l.id,STYLE:l.style,FORMAT:l.format,TILEMATRIXSET:l.set,TILEMATRIX:m.id,TILECOL:c.x,TILEROW:c.y})}
const inCoverage=(l,p)=>!l.bbox||(l.bbox[0]<=p.lng&&p.lng<=l.bbox[2]&&l.bbox[1]<=p.lat&&p.lat<=l.bbox[3]);
function unavailable(i,msg='Image indisponible pour cette période'){$(i?'new-unavailable':'old-unavailable').hidden=false;$(i?'new-unavailable':'old-unavailable').textContent=msg;validPair=false;delete $('comparison-state').dataset.oldHash;delete $('comparison-state').dataset.newHash;$('prepare').disabled=true}
async function fingerprint(i){
 const container=maps[i].getContainer(),rect=container.getBoundingClientRect(),c=document.createElement('canvas');c.width=Math.round(rect.width);c.height=Math.round(rect.height);const ctx=c.getContext('2d',{willReadFrequently:true});
 let count=0;for(const entry of Object.values(raster[i]._tiles)){
  const img=entry.el,r=img.getBoundingClientRect();if(r.right<=rect.left||r.left>=rect.right||r.bottom<=rect.top||r.top>=rect.bottom)continue;
  if(!entry.loaded||!img.complete||!img.naturalWidth)throw Error('Tuile absente');ctx.drawImage(img,r.left-rect.left,r.top-rect.top,r.width,r.height);count++;
 }if(!count)throw Error('Aucune image visible');const data=ctx.getImageData(0,0,c.width,c.height).data;
 let sum=0,sq=0;for(let j=0;j<data.length;j+=4){if(data[j+3]<250)throw Error('Image incomplète');const g=(data[j]+data[j+1]+data[j+2])/3;sum+=g;sq+=g*g}
 const n=data.length/4;if(Math.sqrt(sq/n-(sum/n)**2)<3)throw Error('Image uniforme');
 return {hash:[...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(x=>x.toString(16).padStart(2,'0')).join(''),data};
}
async function verify(){
 const ticket=rendering;try{
  if(!raster[0]||!raster[1])return;
  const a=await fingerprint(0),b=await fingerprint(1);if(ticket!==rendering)return;
  let diff=0,n=0;for(let j=0;j<a.data.length;j+=16){if(Math.abs(a.data[j]-b.data[j])+Math.abs(a.data[j+1]-b.data[j+1])+Math.abs(a.data[j+2]-b.data[j+2])>36)diff++;n++}
  if(a.hash===b.hash||diff/n<.01){unavailable(0,'Comparaison refusée : les deux images semblent identiques. Choisissez une autre période.');$('comparison-state').textContent='Images insuffisamment différentes ; aucune comparaison validée.';return}
  $('old-unavailable').hidden=true;$('new-unavailable').hidden=true;validPair=true;
  $('comparison-state').textContent='Deux ressources IGN distinctes, même cadrage et mêmes dimensions. Empreintes des images affichées : '+a.hash.slice(0,12)+' / '+b.hash.slice(0,12)+'. Les différences visuelles ne constituent pas une détection de changement.';
  $('comparison-state').dataset.oldHash=a.hash;$('comparison-state').dataset.newHash=b.hash;$('prepare').disabled=!(confirmed&&api);
 }catch(e){if(ticket===rendering){unavailable(0);$('comparison-state').textContent='Comparaison non validée : '+e.message+'. Essayez une autre période ou un autre cadrage.'}}
}
const schedule=()=>{clearTimeout(debounce);debounce=setTimeout(verify,250)};
function updateOfficial(){const p=maps[0].getCenter(),old=$('era').value,recent=layers.find(l=>l.current);const params={mode:'doubleMap',x:p.lng,y:p.lat,z:maps[0].getZoom()};if(old&&recent){params.layer1=old;params.layer2=recent.id}$('official').href='https://remonterletemps.ign.fr/comparer/basic?'+new URLSearchParams(params)}
function imagery(){
 rendering++;for(let i=0;i<2;i++){if(raster[i])maps[i].removeLayer(raster[i]);raster[i]=null;unavailable(i,'Vérification de l’image IGN…')}
 const old=layers.find(l=>l.id===$('era').value),recent=layers.find(l=>l.current);if(!old||!recent){unavailable(0);return}
 const zs=Object.keys(old.matrices).map(Number).filter(z=>recent.matrices[z]&&z<=18);if(!zs.length){unavailable(0,'Aucun zoom commun vérifié');return}
 maps.forEach(m=>{m.setMinZoom(Math.min(...zs));m.setMaxZoom(Math.max(...zs))});
 for(const [i,l] of [old,recent].entries()){
  $(i?'new-source':'old-source').textContent=l.period+' · '+l.id+' · style '+l.style+' · '+l.format+' · '+l.set+' · zooms '+Object.keys(l.matrices).join(', ')+' · couverture '+JSON.stringify(l.bbox);
  const Layer=L.TileLayer.extend({getTileUrl(c){return tileURL(l,c)}});
  raster[i]=new Layer('',{minZoom:Math.min(...zs),maxZoom:Math.max(...zs),crossOrigin:'anonymous',attribution:'© IGN / Géoplateforme',updateWhenIdle:true,keepBuffer:0}).addTo(maps[i]);
  raster[i].on('loading',()=>{rendering++;unavailable(i,'Vérification de l’image IGN…')});raster[i].on('load',schedule);raster[i].on('tileerror',()=>{unavailable(i);$('comparison-state').textContent='Image manquante : comparaison non validée. Aucune image récente n’est substituée.'});
 }
 updateOfficial();schedule();
}
async function probe(l,p){
 const z=Math.min(l.max,17),n=2**z,x=Math.floor((p.lng+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(p.lat*Math.PI/180))/Math.PI)/2*n);
 const url=tileURL(l,{x,y,z});if(!url)return false;
 try{const r=await fetch(url,{signal:AbortSignal.timeout(12000)});if(!r.ok)return false;const bitmap=await createImageBitmap(await r.blob());if(bitmap.width!==256||bitmap.height!==256){bitmap.close();return false}const c=document.createElement('canvas');c.width=c.height=256;const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(bitmap,0,0);bitmap.close();const d=ctx.getImageData(0,0,256,256).data;let sum=0,sq=0,n=0;for(let i=0;i<d.length;i+=64){if(d[i+3]<250)return false;const g=(d[i]+d[i+1]+d[i+2])/3;sum+=g;sq+=g*g;n++}return Math.sqrt(sq/n-(sum/n)**2)>3}catch{return false}
}
async function periods(){
 const ticket=++epoch,center=maps[0].getCenter(),prev=$('era').value,old=layers.filter(l=>!l.current&&inCoverage(l,center));
 $('era').disabled=true;unavailable(0,'Vérification des périodes disponibles à cet endroit…');
 const available=[];
 for(let start=0;start<old.length;start+=3){const batch=old.slice(start,start+3),results=await Promise.all(batch.map(l=>probe(l,center)));if(ticket!==epoch)return;batch.forEach((l,i)=>{if(results[i])available.push(l)});if(start+3<old.length)await new Promise(r=>setTimeout(r,300))}
 if(ticket!==epoch)return;
 $('era').replaceChildren(...available.map(l=>new Option(l.period+' · '+l.id,l.id)));$('era').disabled=!available.length;
 if(available.some(l=>l.id===prev))$('era').value=prev;
 if(!available.length){unavailable(0);$('comparison-state').textContent='Aucune période historique vérifiée ici. Déplacez-vous ou consultez IGN ; aucune vue récente n’est substituée.';return}
 imagery();
}

function draw(){maps.forEach((m,i)=>{if(outlines[i])m.removeLayer(outlines[i]);outlines[i]=null;if(!$('outlines').checked)return;outlines[i]=L.geoJSON(candidates,{style:f=>({color:idOf(f)===idOf(selected||{})?'#ffce30':'#59e6ff',weight:idOf(f)===idOf(selected||{})?4:2,fillOpacity:.05}),onEachFeature:(f,l)=>l.on('click',e=>{L.DomEvent.stopPropagation(e);choose(idOf(f))})}).addTo(m)})}
function choose(id){selected=candidates.find(f=>idOf(f)===id)||null;invalidate();$('candidates').value=selected?idOf(selected):'';const p=selected?.properties||{};$('parcel').textContent=selected?['Sélection candidate — à confirmer',p.nom_com||p.nom_commune||'Commune non fournie','INSEE : '+(p.code_insee||'non fourni'),'Section '+(p.section||'non fournie')+' · numéro '+(p.numero||'non fourni'),idOf(selected),'Surface cadastrale : '+(p.contenance==null?'non disponible':p.contenance+' m²')].join('\n'):'Aucune parcelle trouvée. Cliquez sur un terrain ou utilisez sa référence.';draw()}
function setCandidates(features){candidates=features.filter(f=>f.geometry&&idOf(f));selected=null;invalidate();$('candidates').replaceChildren(new Option('Sélectionnez puis confirmez une parcelle',''),...candidates.map(f=>new Option(idOf(f)+' · '+(f.properties?.nom_com||''),idOf(f))));choose('');if(candidates.length===1)choose(idOf(candidates[0]));draw()}
async function point(lng,lat){const t=++selectionGeneration;setCandidates([]);status('Recherche cadastrale au point sélectionné…');try{let fs=(await json(CARTO+'?'+new URLSearchParams({geom:JSON.stringify({type:'Point',coordinates:[lng,lat]})}))).features||[];if(!fs.length){const dy=60/111320,dx=dy/Math.cos(lat*Math.PI/180);fs=(await json(CARTO+'?'+new URLSearchParams({geom:JSON.stringify({type:'Polygon',coordinates:[[[lng-dx,lat-dy],[lng+dx,lat-dy],[lng+dx,lat+dy],[lng-dx,lat+dy],[lng-dx,lat-dy]]]})}))).features||[]}
 if(t!==selectionGeneration)return;setCandidates(fs.slice(0,30));status(fs.length?'Candidats affichés. Aucune correspondance avec l’adresse n’est certaine.':'Aucune parcelle trouvée. Cliquez sur le terrain ou saisissez sa référence.');}catch(e){if(t===selectionGeneration)status(e.message,true)}}
async function search(e){e?.preventDefault();const t=++generation;selectionGeneration++;setCandidates([]);$('search').disabled=true;status('Recherche d’adresse…');$('address-choices').replaceChildren();try{const fs=(await json('https://data.geopf.fr/geocodage/search?'+new URLSearchParams({q:$('address').value,index:'address',limit:5}))).features||[];if(t!==generation)return;if(!fs.length)throw Error('Adresse introuvable');for(const f of fs){const b=node('button',f.properties.label);b.onclick=()=>useAddress(f);$('address-choices').append(b)}await useAddress(fs[0]);}catch(e){if(t===generation)status(e.message,true)}finally{if(t===generation)$('search').disabled=false}}
async function useAddress(f){const [lon,lat]=f.geometry.coordinates;$('found-address').textContent=f.properties.label;maps[0].setView([lat,lon],17);maps[1].setView([lat,lon],17);periods();await point(lon,lat)}
$('search-form').onsubmit=search;$('candidates').onchange=()=>choose($('candidates').value);$('era').onchange=()=>{prepared=null;$('checkout').disabled=true;imagery()};$('outlines').onchange=draw;
$('identifier-form').onsubmit=async e=>{e.preventDefault();const t=++selectionGeneration;generation++;const id=$('identifier').value.replace(/[\s-]/g,'').toUpperCase();setCandidates([]);if(!/^(?:[0-9]{5}|2[AB][0-9]{3})[0-9]{3}[A-Z0-9]{2}[0-9]{4}$/.test(id)){status('Identifiant cadastral invalide (14 caractères requis).',true);return}status('Recherche de la référence cadastrale…');try{const fs=(await json(CARTO+'?'+new URLSearchParams({code_insee:id.slice(0,5),section:id.slice(8,10),numero:id.slice(10)}))).features||[];if(t!==selectionGeneration)return;setCandidates(fs.filter(f=>idOf(f)===id));if(selected){$('fit').click();periods()}status(selected?'Référence exacte retrouvée. Vérifiez et confirmez le contour.':'Aucune parcelle avec cette référence exacte.',!selected)}catch(e){if(t===selectionGeneration)status(e.message,true)}};
$('fit').onclick=()=>{if(selected){const b=L.geoJSON(selected).getBounds().pad(1);maps.forEach(m=>m.fitBounds(b,{maxZoom:18}))}};
$('confirm').onclick=()=>{if(!selected)return;confirmed=true;$('confirm').disabled=true;$('parcel').textContent=$('parcel').textContent.replace('Sélection candidate — à confirmer','Parcelle confirmée par vous');$('prepare').disabled=!(api&&validPair);$('report-status').textContent=api?'Parcelle confirmée. Vérifiez les données avant tout paiement test.':'Parcelle confirmée. Serveur de rapports non connecté : export et paiement indisponibles.'};
$('prepare').onclick=async()=>{const parcel=idOf(selected||{}),old=$('era').value;if(!confirmed||!validPair)return;prepared=null;$('checkout').disabled=true;$('prepare').disabled=true;status('Vérification des images et génération préalable HTML/PDF…');try{const p=await post('/api/previews',{parcel_id:parcel,confirmed:true,address:$('found-address').textContent||$('address').value,historical_resource:old});if(!confirmed||idOf(selected||{})!==parcel||$('era').value!==old)return;prepared=p;$('report-status').textContent=p.summary+' Paiement sandbox uniquement.';$('checkout').disabled=!p.payments_enabled;status('Dossier préparé. Les données essentielles ont été générées avant paiement.');}catch(e){$('report-status').textContent=e.message;status(e.message,true)}finally{$('prepare').disabled=!(api&&confirmed&&validPair)}};
$('checkout').onclick=async()=>{if(!prepared)return;$('checkout').disabled=true;try{const d=await post('/api/checkout',{preview_token:prepared.preview_token});sessionStorage.setItem('sitehistory-order',JSON.stringify({id:d.order_id,token:d.order_token}));location.assign(d.url)}catch(e){status(e.message,true);$('checkout').disabled=false}};
async function delivery(){const raw=sessionStorage.getItem('sitehistory-order');if(!raw||!api)return;let o;try{o=JSON.parse(raw)}catch{return}const r=await fetch(api+'/api/orders/'+o.id,{headers:{Authorization:'Bearer '+o.token}});if(!r.ok)return;const d=await r.json();$('report-status').textContent=d.message;$('delivery').replaceChildren();for(const format of ['html','pdf'])if(d.downloads?.[format]){const a=node('a','Télécharger '+format.toUpperCase());a.href=api+d.downloads[format];a.rel='noreferrer';$('delivery').append(a)}if(d.retryable){const b=node('button','Reprendre la livraison');b.onclick=async()=>{await post('/api/orders/'+o.id+'/retry',{order_token:o.token});await delivery()};$('delivery').append(b)}if(d.status==='pending'||d.status==='paid')setTimeout(()=>delivery().catch(()=>{}),4000)}
delivery().catch(()=>{$('report-status').textContent='Livraison momentanément inaccessible. Rechargez cette page pour reprendre sans repayer.'});
try{
 if(!window.L)throw Error('Bibliothèque cartographique indisponible');
 maps=[L.map('map-old',{zoomAnimation:false,fadeAnimation:false}),L.map('map-new',{zoomAnimation:false,fadeAnimation:false})];
 maps.forEach(m=>m.setView([49.15,1.53],17));let syncing=false;
 maps.forEach((m,i)=>{m.on('move',()=>{if(syncing)return;syncing=true;maps[1-i].setView(m.getCenter(),m.getZoom(),{animate:false});syncing=false});m.on('movestart',()=>{rendering++;unavailable(0,'Cadrage en cours…');unavailable(1,'Cadrage en cours…')});m.on('moveend',()=>{updateOfficial();schedule()});m.on('click',e=>point(e.latlng.lng,e.latlng.lat))});
 layers=await catalogue();periods();status('Catalogue IGN vérifié. Choisissez votre adresse ou référence.');await search();
}catch(e){status('Exploration indisponible : '+e.message+'. Réessayez ou consultez directement IGN.',true)}
})();
