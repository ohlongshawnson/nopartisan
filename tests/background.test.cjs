const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const foundation = JSON.parse(fs.readFileSync('extension/foundational.json'));
const DEFAULT = 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json';
function setup(initial = {}) {
 const state=structuredClone(initial), events={installed:[],startup:[],changed:[],added:[],alarm:[]};
 const requests=[], writes=[]; let message, opened=0, allowed=true, response={schemaVersion:1,version:'downloaded',keywords:['new politician']}, fail=false, gate;
 const alarms={};
 const browser={
  storage:{local:{get:async keys=>keys==null?{...state}:Object.fromEntries((Array.isArray(keys)?keys:[keys]).filter(k=>k in state).map(k=>[k,state[k]])),set:async value=>{writes.push(value);Object.assign(state,structuredClone(value));}},onChanged:{addListener:f=>events.changed.push(f)}},
  permissions:{contains:async()=>allowed,onAdded:{addListener:f=>events.added.push(f)}},
  alarms:{clear:async name=>{delete alarms[name];},create:(name,value)=>{alarms[name]=value;},onAlarm:{addListener:f=>events.alarm.push(f)}},
  runtime:{id:'test',getURL:p=>'moz-extension://test/'+p,openOptionsPage:async()=>{opened++;},onInstalled:{addListener:f=>events.installed.push(f)},onStartup:{addListener:f=>events.startup.push(f)},onMessage:{addListener:f=>message=f}},
  menus:{remove:async()=>{},create(){},onClicked:{addListener(){}}}
 };
 const ctx=vm.createContext({browser,URL,AbortSignal,TextDecoder,Uint8Array,fetch:async(url,options)=>{
  if(url==='moz-extension://test/foundational.json')return new Response(JSON.stringify(foundation));
  requests.push({url,options}); if(gate)await gate;
  if(fail)throw new TypeError('Network unavailable');
  return response instanceof Response?response:new Response(JSON.stringify(response));
 }});
 for(const file of ['core.js','background.js'])vm.runInContext(fs.readFileSync('extension/'+file,'utf8'),ctx);
 return {state,events,requests,writes,alarms,opened:()=>opened,install:reason=>events.installed[0]({reason}),startup:()=>events.startup[0](),alarm:()=>events.alarm[0]({name:'keywords'}),manual:()=>message({type:'update'},{id:'test',url:'moz-extension://test/options.html'}),untrusted:()=>message({type:'update'},{id:'test',url:'https://x.com/home'}),allow:v=>allowed=v,fail:v=>fail=v,response:v=>response=v,gate:v=>gate=v};
}
test('fresh install automatically downloads validated schema 1, merges foundation, and atomically publishes cache',async()=>{
 const c=setup();await c.install('install');
 assert.equal(c.state.settings.autoUpdate,true);assert.equal(c.state.settings.enabled,true);assert.deepEqual(c.state.settings.custom,[]);
 assert.equal(c.requests.length,1);assert.equal(c.requests[0].url,DEFAULT);assert.equal(c.requests[0].options.credentials,'omit');assert.equal(c.requests[0].options.referrerPolicy,'no-referrer');assert.equal(c.requests[0].options.redirect,'error');
 assert.ok(foundation.keywords.every(k=>c.state.remoteList.keywords.includes(k)));
 assert.equal(c.state.downloadedKeywordCount,1);assert.equal(c.state.updateStatus,'current');assert.equal(c.state.updateError,'');assert.equal(c.opened(),1);
 const write=c.writes.find(v=>v.remoteList);assert.ok(write.lastUpdate);assert.ok(write.nextUpdate);assert.equal(write.updateError,'');assert.ok(c.alarms.keywords.when>Date.now()+23.9*3600000);
});
test('initial download is independent of bundled filtering and offline failures schedule a one-hour retry',async()=>{
 const c=setup();c.fail(true);await c.install('install');
 assert.equal(c.state.settings.enabled,true);assert.equal(c.state.remoteList,undefined);assert.match(c.state.updateError,/Network unavailable/);assert.equal(c.state.updateStatus,'error');
 assert.ok(c.alarms.keywords.when>Date.now()+59*60000);assert.ok(c.alarms.keywords.when<Date.now()+61*60000);
 c.fail(false);await c.alarm();assert.ok(c.state.remoteList);assert.equal(c.state.updateError,'');
});
test('existing opt-outs, missing legacy autoUpdate, settings, custom URLs and caches survive migration and startup',async()=>{
 for(const settings of [{enabled:false,custom:['personal'],source:'https://raw.githubusercontent.com/team/nopartisan/main/custom.json',autoUpdate:false},{enabled:true,custom:['legacy'],source:''}]){
  const c=setup({settings,remoteList:{schemaVersion:1,version:'cached',keywords:['cached']}});await c.install('update');await c.startup();await c.alarm();
  assert.deepEqual(c.state.settings,settings);assert.equal(c.state.remoteList.version,'cached');assert.equal(c.requests.length,0);assert.equal(c.alarms.keywords,undefined);
 }
 const c=setup({remoteList:{schemaVersion:1,version:'legacy',keywords:['cached']}});await c.install('update');assert.equal(c.state.settings.autoUpdate,false);assert.equal(c.requests.length,0);
});
test('opted-in custom source is preserved and fetched without replacing user settings',async()=>{
 const settings={enabled:false,custom:['personal'],source:'https://raw.githubusercontent.com/team/nopartisan/main/custom.json',autoUpdate:true};
 const c=setup({settings});await c.install('update');assert.equal(c.requests[0].url,settings.source);assert.deepEqual(c.state.settings,settings);
});
test('restart schedules the stored due time without fetching early and catches up when overdue',async()=>{
 const nextUpdate=Date.now()+6*3600000;const c=setup({settings:{autoUpdate:true},nextUpdate,lastUpdate:new Date().toISOString(),remoteList:{schemaVersion:1,version:'cached',keywords:['cached']}});
 await c.startup();assert.equal(c.requests.length,0);assert.equal(c.alarms.keywords.when,nextUpdate);assert.equal(c.state.remoteList.version,'cached');
 c.state.nextUpdate=Date.now()-1;await c.startup();assert.equal(c.requests.length,1);
});
test('denied permission and unavailable, invalid, empty or oversized downloads preserve known-good filters',async()=>{
 const cached={schemaVersion:1,version:'cached',keywords:['known good']};
 for(const kind of ['permission','network','invalid','empty','oversize']){
  const c=setup({settings:{autoUpdate:true},remoteList:cached});
  if(kind==='permission')c.allow(false);if(kind==='network')c.fail(true);if(kind==='invalid')c.response({bad:true});if(kind==='empty')c.response({schemaVersion:1,version:'empty',keywords:[]});if(kind==='oversize')c.response(new Response(new Uint8Array(1000001)));
  const result=await c.manual();assert.ok(result.error,kind);assert.deepEqual(c.state.remoteList,cached);assert.ok(c.state.updateError);assert.equal(c.untrusted(),undefined);if(kind==='permission')assert.equal(c.requests.length,0);
 }
});
test('concurrent downloads share one request and obsolete sources, opt-outs or revoked permission cannot publish',async()=>{
 for(const changed of ['source','optout','permission']){
  const c=setup({settings:{source:DEFAULT,autoUpdate:true}});let release;c.gate(new Promise(r=>release=r));
  const pending=c.alarm();while(!c.requests.length)await new Promise(r=>setTimeout(r,0));const second=c.manual();
  if(changed==='source')c.state.settings={source:'https://raw.githubusercontent.com/team/nopartisan/main/custom.json',autoUpdate:true};
  if(changed==='optout')c.state.settings={source:DEFAULT,autoUpdate:false};if(changed==='permission')c.allow(false);
  release();await pending;assert.ok((await second).error);assert.equal(c.requests.length,1);assert.equal(c.state.remoteList,undefined);
 }
});
