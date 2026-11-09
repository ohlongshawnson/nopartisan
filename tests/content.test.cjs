const { test } = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const fs = require('node:fs');
const wait = () => new Promise(resolve => setTimeout(resolve, 250));
async function waitFor(predicate, timeout=5000) {
 const until=Date.now()+timeout;
 while(Date.now()<until){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,25));}
 assert.ok(predicate(),'condition not reached before timeout');
}
test('dynamic posts, reveal, recycled cards, and disabling', async () => {
 const dom = new JSDOM('<body><article data-testid="tweet">MAGA rally</article><article data-testid="tweet">A magazine review</article></body>', {url:'https://x.com/home',runScripts:'outside-only'});
 const w = dom.window; let change; let settings = {enabled:true,custom:[]};
 w.browser = {runtime:{id:'test',onMessage:{addListener(){}},getURL:p=>p},storage:{local:{get:async()=>({settings})},onChanged:{addListener:f=>change=f}}};
 w.fetch = async () => ({json:async()=>({schemaVersion:1,version:'v',keywords:['MAGA']})});
 w.eval(fs.readFileSync('extension/core.js','utf8')); w.eval(fs.readFileSync('extension/x-adapter.js','utf8')); w.eval(fs.readFileSync('extension/content.js','utf8'));
 try {
 await wait(); const post = w.document.querySelector('article');
 assert.ok(post.classList.contains('nopartisan-filtered'));
 assert.equal(w.document.querySelectorAll('.nopartisan-notice').length,1);
 await wait(); assert.ok(post.classList.contains('nopartisan-filtered'));
 w.document.querySelector('button').click(); await wait(); assert.equal(post.classList.contains('nopartisan-filtered'),false);
 post.textContent='Another MAGA rally'; await wait(); assert.ok(post.classList.contains('nopartisan-filtered'));
 post.textContent='A peaceful garden'; await wait(); assert.equal(post.classList.contains('nopartisan-filtered'),false);
 const fresh = w.document.createElement('article'); fresh.dataset.testid='tweet'; fresh.textContent='MAGA'; w.document.body.append(fresh); await wait(); assert.ok(fresh.classList.contains('nopartisan-filtered'));
 settings={enabled:false,custom:[]};change({settings:{}},'local');await wait();assert.equal(w.document.querySelectorAll('.nopartisan-filtered').length,0);
 } finally {w.close();}
});

test('fresh offline installation filters from the complete bundled list', async () => {
 const terms = require('../extension/keywords.json');
 const dom = new JSDOM('<body><article data-testid="tweet">Donald J. Trump spoke today</article></body>', {url:'https://x.com/home',runScripts:'outside-only'});
 const w = dom.window;
 w.browser = {runtime:{id:'test',onMessage:{addListener(){}},getURL:p=>`moz-extension://test/${p}`},storage:{local:{get:async()=>({})},onChanged:{addListener(){}}}};
 w.fetch = async url => ({json:async()=>JSON.parse(fs.readFileSync(url.endsWith('keywords.json')?'extension/keywords.json':url,'utf8'))});
 w.eval(fs.readFileSync('extension/core.js','utf8')); w.eval(fs.readFileSync('extension/x-adapter.js','utf8')); w.eval(fs.readFileSync('extension/content.js','utf8'));
 try {
  await waitFor(()=>w.document.querySelector('article').classList.contains('nopartisan-filtered'));
  assert.ok(terms.keywords.length > 800);
  assert.ok(w.document.querySelector('article').classList.contains('nopartisan-filtered'));
  assert.equal(w.document.querySelectorAll('.nopartisan-notice').length,1);
 } finally {w.close();}
});

test('a successful list update rescans tabs that were already open', async () => {
 const dom = new JSDOM('<body><article data-testid="tweet">A cabinet announcement today</article></body>', {url:'https://x.com/home',runScripts:'outside-only'});
 const w = dom.window; let changed;
 w.browser = {runtime:{id:'test',onMessage:{addListener(){}},getURL:p=>p},storage:{local:{get:async()=>({settings:{enabled:true,custom:[]}})},onChanged:{addListener:fn=>changed=fn}}};
 w.fetch = async () => ({json:async()=>({schemaVersion:1,version:'bundled',keywords:['not present']})});
 w.eval(fs.readFileSync('extension/core.js','utf8')); w.eval(fs.readFileSync('extension/x-adapter.js','utf8')); w.eval(fs.readFileSync('extension/content.js','utf8'));
 try {
  await wait(); const post=w.document.querySelector('article');
  assert.equal(post.classList.contains('nopartisan-filtered'),false);
  const oldGet=w.browser.storage.local.get;
  w.browser.storage.local.get=async keys=>keys.includes('remoteList')?{remoteList:{schemaVersion:1,version:'updated',keywords:['cabinet announcement']}}:{settings:{enabled:true,custom:[]}};
  changed({remoteList:{}},'local'); await wait();
  assert.ok(post.classList.contains('nopartisan-filtered'));
  w.browser.storage.local.get=oldGet;
 } finally {w.close();}
});
