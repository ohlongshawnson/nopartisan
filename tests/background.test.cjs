const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
test('updates retain known-good data on failure and reject messages from feeds', async () => {
 let listener; let response = {schemaVersion:1,version:'new',keywords:['campaign']};
 const data = {settings:{source:'https://raw.githubusercontent.com/owner/nopartisan/main/keywords/politics.json'},remoteList:{version:'old'}};
 const browser = {menus:{onClicked:{addListener(){}}},storage:{local:{get:async key=> key === 'settings' ? {settings:data.settings} : data,set:async value=>Object.assign(data,value)},onChanged:{addListener(){}}},permissions:{contains:async()=>true},alarms:{clear:async()=>{},create(){},onAlarm:{addListener(){}}},action:{onClicked:{addListener(){}}},runtime:{id:'test',getURL:p=>'moz-extension://test/'+p,onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener:f=>listener=f}}};
 const ctx=vm.createContext({browser,URL,AbortSignal,TextDecoder,Uint8Array,fetch:async()=>new Response(JSON.stringify(response))});
 vm.runInContext(fs.readFileSync('extension/core.js','utf8'),ctx);vm.runInContext(fs.readFileSync('extension/background.js','utf8'),ctx);
 const sender={id:'test',url:'moz-extension://test/options.html'};
 assert.equal(listener({type:'update'},{id:'test',url:'https://x.com/home'}),undefined);
 response={bad:true};assert.ok((await listener({type:'update'},sender)).error);assert.equal(data.remoteList.version,'old');assert.match(data.updateError,/Invalid keyword list/);
 response={schemaVersion:1,version:'new',keywords:['campaign']};assert.equal((await listener({type:'update'},sender)).version,'new');assert.equal(data.remoteList.version,'new');
});

test('an empty legacy source safely resolves to the maintained default and missing permission blocks downloads', async () => {
 let listener; let requestedUrl=''; let allowed=true;
 const data={settings:{enabled:true,autoUpdate:false},remoteList:{schemaVersion:1,version:'known-good',keywords:['previous']}};
 const browser={menus:{onClicked:{addListener(){}}},storage:{local:{get:async key=>key==='settings'?{settings:data.settings}:data,set:async value=>Object.assign(data,value)},onChanged:{addListener(){}}},permissions:{contains:async()=>allowed},alarms:{clear:async()=>{},create(){},onAlarm:{addListener(){}}},action:{onClicked:{addListener(){}}},runtime:{id:'test',getURL:p=>'moz-extension://test/'+p,onInstalled:{addListener(){}},onStartup:{addListener(){}},onMessage:{addListener:f=>listener=f}}};
 const ctx=vm.createContext({browser,URL,AbortSignal,TextDecoder,Uint8Array,fetch:async url=>{requestedUrl=url;return new Response(JSON.stringify({schemaVersion:1,version:'maintained',keywords:['new phrase']}));}});
 vm.runInContext(fs.readFileSync('extension/core.js','utf8'),ctx);vm.runInContext(fs.readFileSync('extension/background.js','utf8'),ctx);
 const sender={id:'test',url:'moz-extension://test/options.html'};
 allowed=false;assert.match((await listener({type:'update'},sender)).error,/Grant GitHub access/);
 assert.equal(requestedUrl,'');assert.equal(data.remoteList.version,'known-good');
 allowed=true;assert.equal((await listener({type:'update'},sender)).version,'maintained');
 assert.equal(requestedUrl,'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json');
});

test('first installation opens permission guidance without downloading or changing existing settings', async () => {
 const installed = []; let opened = 0; let fetches = 0;
 const settings = { enabled: false, custom: ['personal'], autoUpdate: false, source: '' };
 const browser = {
  runtime: { id: 'test', getURL: p => p, openOptionsPage: async () => { opened++; }, onInstalled: { addListener: f => installed.push(f) }, onStartup: { addListener() {} }, onMessage: { addListener() {} } },
  storage: { local: { get: async () => ({settings}) }, onChanged: { addListener() {} } },
  alarms: { clear: async () => {}, onAlarm: { addListener() {} } }, menus: { onClicked: { addListener() {} } }
 };
 const ctx = vm.createContext({ browser, fetch: async () => { fetches++; } });
 vm.runInContext(fs.readFileSync('extension/core.js','utf8'),ctx);
 vm.runInContext(fs.readFileSync('extension/background.js','utf8'),ctx);
 await installed[0]({reason:'install'});
 assert.equal(opened,1); assert.equal(fetches,0);
 await installed[0]({reason:'update'});
 assert.equal(opened,1); assert.deepEqual(settings.custom,['personal']); assert.equal(settings.enabled,false);
});
