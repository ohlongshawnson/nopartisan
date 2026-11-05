const { test } = require('node:test');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const fs = require('node:fs');
const wait = () => new Promise(resolve => setTimeout(resolve, 250));
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
