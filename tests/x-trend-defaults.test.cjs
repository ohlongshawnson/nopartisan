const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const wait=()=>new Promise(r=>setTimeout(r,180));
async function setup() {
 const dom=new JSDOM(fs.readFileSync('tests/fixtures/x-alito-trend.html','utf8'),{url:'https://x.com/home',runScripts:'outside-only'});
 const w=dom.window; let changed, message, target; const stored={}; const requests=[], logs=[];
 w.console.info=(...args)=>logs.push(args);
 w.browser={runtime:{id:'test',getManifest:()=>({version:'0.3.0'}),getURL:p=>'moz-extension://test/'+p,onMessage:{addListener:f=>message=f}},menus:{getTargetElement:()=>target},storage:{local:{get:async()=>stored},onChanged:{addListener:f=>changed=f}}};
 w.fetch=async url=>{requests.push(url); assert.ok(url.startsWith('moz-extension://test/'),'no internet requests');return {json:async()=>JSON.parse(fs.readFileSync('extension/'+url.split('/').pop(),'utf8'))};};
 const style=w.document.createElement('style');style.textContent=fs.readFileSync('extension/content.css','utf8');w.document.head.append(style);
 for(const file of ['core.js','x-adapter.js','content.js'])w.eval(fs.readFileSync('extension/'+file,'utf8'));
 for(let i=0;i<100 && (!w.NOpartisanDiagnostics.initialized || !w.NOpartisanDiagnostics.candidates);i++) await new Promise(r=>setTimeout(r,30));
 return {w,stored,requests,logs,hidden:id=>w.getComputedStyle(w.document.getElementById(id)).display==='none',save:async value=>{Object.assign(stored,value);changed(Object.fromEntries(Object.keys(value).map(k=>[k,{}])),'local');await wait();},inspect:async id=>{target=w.document.getElementById(id);return JSON.parse(JSON.stringify(await message({type:'inspectPost',targetElementId:1},{id:'test'})));},close:()=>w.close()};
}
test('offline defaults automatically hide Politics · Trending / Justice Samuel Alito and preserve unrelated cards',async()=>{
 const c=await setup();try{
  assert.equal(c.w.NOpartisanDiagnostics.initialized,true);assert.equal(c.w.NOpartisanDiagnostics.runtimeErrors,0);
  assert.deepEqual(c.stored,{});assert.equal(c.hidden('alito'),true);assert.equal(c.hidden('fursuit'),false);assert.equal(c.hidden('happening'),false);assert.equal(c.hidden('unrelated'),false);
  const report=await c.inspect('alito');assert.equal(report.candidateType,'trend');assert.equal(report.categoryMatched,true);assert.equal(report.computedHidden,true);assert.equal(report.build,'trend-foundation-1');
  assert.ok(report.extracted.categoryText.includes('Politics'));assert.match(report.extracted.topicText,/Justice Samuel Alito/);
  assert.deepEqual(report.keywordChecks.find(k=>k.keyword==='politics'),{keyword:'politics',active:true,extracted:true,presentInDOMText:true});
  assert.deepEqual(report.keywordChecks.find(k=>k.keyword==='justice samuel alito'),{keyword:'justice samuel alito',active:false,extracted:true,presentInDOMText:true});
  assert.ok(c.requests.every(url=>url.startsWith('moz-extension:')));
  assert.equal(JSON.stringify(c.logs).includes('Samuel Alito'),false);
 }finally{c.close();}
});
test('explicit political category is independent of keyword matcher; News and Gaming do not classify as politics',async()=>{
 const c=await setup();try{
  const X=c.w.NOpartisan.X;const extracted=X.extract(c.w.document.getElementById('alito'));
  assert.equal(X.politicalCategory(extracted),true);assert.equal(c.w.NOpartisan.matcher([])(extracted.outerText),false);
  assert.equal(c.w.NOpartisan.matcher(['politics'])(extracted.outerText),true);
  assert.equal(c.w.NOpartisan.matcher(['Justice Samuel Alito'])(extracted.outerText),true);
  for(const category of ['Gaming · Trending','News · Trending','Technology · Trending','Entertainment · Trending']) {
   c.w.document.getElementById('alito').innerHTML=`<div><span>${category}</span></div><div>Grand Theft Auto VI</div>`;
   await wait();assert.equal(c.hidden('alito'),false,category);assert.equal(X.politicalCategory(X.extract(c.w.document.getElementById('alito'))),false);
  }
 }finally{c.close();}
});
test('foundation filters posts and survives downloaded lists with no foundational terms',async()=>{
 const c=await setup();try{
  c.w.document.getElementById('unrelated').textContent='The presidential election and senate ballot';await wait();assert.equal(c.hidden('unrelated'),true);
  await c.save({remoteList:{schemaVersion:1,version:'names-only-update',keywords:['A Newly Collected Politician']}});
  assert.equal(c.hidden('unrelated'),true);assert.equal(c.hidden('alito'),true);
  const report=await c.inspect('alito');assert.equal(report.list.source,'downloaded');assert.equal(report.keywordChecks.find(k=>k.keyword==='politics').active,true);
 }finally{c.close();}
});
test('dynamic category changes, Reveal and disabling restore only the individual trend',async()=>{
 const c=await setup();try{
  c.w.document.getElementById('alito').previousElementSibling.querySelector('button').click();await wait();assert.equal(c.hidden('alito'),false);assert.equal((await c.inspect('alito')).revealed,true);
  c.w.document.getElementById('alito').querySelector('div:nth-child(2)').textContent='Another political topic';await wait();assert.equal(c.hidden('alito'),true);
  c.w.document.getElementById('happening').insertAdjacentHTML('beforeend','<div id="newTrend" data-testid="trend"><div>Politics · Trending</div><div>Unknown title</div></div>');await wait();assert.equal(c.hidden('newTrend'),true);
  await c.save({settings:{enabled:false,custom:[]}});assert.equal(c.hidden('alito'),false);assert.equal(c.hidden('newTrend'),false);assert.equal((await c.inspect('alito')).filteringEnabled,false);
  await c.save({settings:{enabled:true,custom:[]}});assert.equal(c.hidden('alito'),true);assert.equal(c.hidden('fursuit'),false);
 }finally{c.close();}
});
test('trend diagnostics distinguish recognition, absent text, absent keyword, and CSS failure',async()=>{
 const c=await setup();try{
  assert.equal((await c.inspect('happening')).recognized,false);
  const r=await c.inspect('fursuit');assert.equal(r.matched,false);assert.equal(r.keywordChecks.find(k=>k.keyword==='politics').active,true);assert.equal(r.keywordChecks.find(k=>k.keyword==='politics').extracted,false);
  c.w.document.querySelector('style').remove();const css=await c.inspect('alito');assert.equal(css.matched,true);assert.equal(css.currentlyHidden,true);assert.equal(css.computedHidden,false);
 }finally{c.close();}
});
