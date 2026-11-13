const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const settle = () => new Promise(resolve => setTimeout(resolve, 40));
const bundle = JSON.parse(fs.readFileSync('extension/keywords.json', 'utf8'));

async function openOptions({ settings, remoteList, granted = false, allow = true, lastUpdate, updateError, downloadedKeywordCount, updateStatus, nextUpdate } = {}) {
  const state = { settings, remoteList, lastUpdate, updateError, downloadedKeywordCount, updateStatus, nextUpdate };
  const changes = [];
  const requested = [];
  const dom = new JSDOM(fs.readFileSync('extension/options.html', 'utf8'), { runScripts: 'outside-only', url: 'moz-extension://test/options.html' });
  const w = dom.window;
  w.fetch = async url => ({ json: async () => JSON.parse(fs.readFileSync('extension/'+url.split('/').pop(), 'utf8')) });
  w.browser = {
    storage: { local: {
      get: async keys => {
        if (!keys) return state;
        return Object.fromEntries((Array.isArray(keys) ? keys : [keys]).filter(key => key in state).map(key => [key, state[key]]));
      },
      set: async value => Object.assign(state, value),
      remove: async keys => keys.forEach(key => delete state[key])
    }, onChanged: { addListener: fn => changes.push(fn) } },
    permissions: { onAdded: { addListener() {} }, onRemoved: { addListener() {} }, contains: async () => granted, request: async value => { requested.push(value); granted = allow; return allow; } },
    runtime: { getURL: path => `moz-extension://test/${path}`, sendMessage: async () => {
      state.remoteList = { schemaVersion: 1, version: 'downloaded-v2', keywords: ['updated list'] };
      state.lastUpdate = '2026-11-06T12:00:00.000Z'; state.updateError = '';
      for (const fn of changes) fn({ remoteList: {}, lastUpdate: {}, updateError: {} }, 'local');
      return { version: 'downloaded-v2' };
    } }
  };
  for (const file of ['core.js', 'options.js']) w.eval(fs.readFileSync(`extension/${file}`, 'utf8'));
  await settle();
  return { dom, state, requested };
}

test('fresh initialized settings report bundled filters and automatic updates without a runtime permission request', async () => {
  const { dom, requested } = await openOptions({settings:{enabled:true,autoUpdate:true,custom:[]},granted:true});
  try {
    const doc = dom.window.document;
    assert.equal(doc.getElementById('enabled').checked, true);
    assert.equal(doc.getElementById('autoUpdate').checked, true);
    assert.equal(doc.getElementById('source').value, 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json');
    assert.match(doc.getElementById('listInfo').textContent, new RegExp(`Current filters: ${bundle.keywords.length} unique words and phrases`));
    assert.match(doc.getElementById('listInfo').textContent, /ready offline/);
    assert.deepEqual(requested, []);
  } finally { dom.window.close(); }
});

test('older installations preserve personal terms, custom source, filtering choices, and update opt-out', async () => {
  const saved = { enabled: false, showPlaceholders: false, custom: ['Mike Lee'], source: 'https://raw.githubusercontent.com/team/nopartisan/main/custom.json', autoUpdate: false };
  const { dom, state } = await openOptions({ settings: saved, remoteList: { schemaVersion: 1, version: 'cached', keywords: ['cached phrase'] } });
  try {
    const doc = dom.window.document;
    assert.equal(doc.getElementById('showPlaceholders').checked, false);
    assert.equal(doc.getElementById('source').value, saved.source);
    assert.match(doc.getElementById('listInfo').textContent, /Downloaded keywords: 1/);
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(state.settings.enabled, false);
    assert.equal(state.settings.autoUpdate, false);
    assert.deepEqual(Array.from(state.settings.custom), ['Mike Lee']);
    assert.equal(state.settings.source, saved.source);
    assert.equal(state.remoteList.version, 'cached');
  } finally { dom.window.close(); }
});

test('revoked update permission can be requested from a user action; denial keeps filtering usable', async () => {
  const denied = await openOptions({ settings: { enabled: true, custom: ['personal'], source: '', autoUpdate: false }, allow: false });
  try {
    const doc = denied.dom.window.document;
    doc.getElementById('autoUpdate').checked = true;
    doc.getElementById('settings').dispatchEvent(new denied.dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(denied.state.settings.autoUpdate, false);
    assert.equal(denied.state.settings.enabled, true);
    assert.deepEqual(Array.from(denied.state.settings.custom), ['personal']);
    assert.match(doc.getElementById('status').textContent, /access was declined/);
    assert.equal(denied.requested.length, 1);
  } finally { denied.dom.window.close(); }

  const approved = await openOptions({ settings: { enabled: true, custom: [], source: '', autoUpdate: false }, allow: true });
  try {
    const doc = approved.dom.window.document;
    doc.getElementById('autoUpdate').checked = true;
    doc.getElementById('settings').dispatchEvent(new approved.dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(approved.state.settings.autoUpdate, true);
    assert.equal(approved.state.settings.source, 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json');
    assert.equal(approved.requested.length, 1);
  } finally { approved.dom.window.close(); }
});

test('manual update requests access in a click, then displays the refreshed list version and success time', async () => {
  const { dom, state, requested } = await openOptions({ settings: { enabled: true, custom: [], source: '', autoUpdate: false }, allow: true });
  try {
    dom.window.document.getElementById('update').dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true }));
    await settle(); await settle();
    assert.equal(requested.length, 1);
    assert.equal(state.remoteList.version, 'downloaded-v2');
    assert.match(dom.window.document.getElementById('listInfo').textContent, /Using the saved update \(downloaded-v2\)/);
    assert.match(dom.window.document.getElementById('listInfo').textContent, /Last successful update:/);
  } finally { dom.window.close(); }
});

test('failed download status keeps the last valid list visible', async () => {
  const { dom } = await openOptions({
    remoteList: { schemaVersion: 1, version: 'last-good', keywords: ['one phrase'] },
    lastUpdate: '2026-11-05T18:51:21.317Z', updateError: 'Network unavailable.'
  });
  try {
    const info = dom.window.document.getElementById('listInfo').textContent;
    assert.match(info, /Using the saved update \(last-good\)/);
    assert.match(info, /Last successful update:/);
    assert.match(info, /Last update error: Network unavailable/);
  } finally { dom.window.close(); }
});

test('missing website access is visible and requests only the selected site in a click', async () => {
  const { dom, requested } = await openOptions({ allow: false });
  try {
    const doc = dom.window.document;
    assert.match(doc.getElementById('siteAccess').textContent, /X: Access missing; filtering cannot run/);
    assert.equal(doc.getElementById('siteAccess').querySelectorAll('button').length, 3);
    assert.equal(requested.length, 0);
    doc.getElementById('siteAccess').querySelector('button').click();
    await settle();
    assert.deepEqual(JSON.parse(JSON.stringify(requested)), [{ origins: ['https://x.com/*'] }]);
    assert.match(doc.getElementById('status').textContent, /X access was declined/);
    assert.equal(doc.getElementById('enabled').checked, true);
  } finally { dom.window.close(); }
});

test('granted website access needs no request and granting a missing site explains refreshing tabs', async () => {
  const ready = await openOptions({ granted: true });
  try {
    assert.match(ready.dom.window.document.getElementById('siteAccess').textContent, /X: Access granted/);
    assert.equal(ready.dom.window.document.getElementById('siteAccess').querySelectorAll('button').length, 0);
    assert.equal(ready.requested.length, 0);
  } finally { ready.dom.window.close(); }
  const missing = await openOptions({ allow: true });
  try {
    missing.dom.window.document.getElementById('siteAccess').querySelector('button').click();
    await settle();
    assert.match(missing.dom.window.document.getElementById('status').textContent, /Refresh your X tabs/);
    assert.deepEqual(JSON.parse(JSON.stringify(missing.requested)), [{ origins: ['https://x.com/*'] }]);
  } finally { missing.dom.window.close(); }
});

test('update status reports deduplicated active, foundation and downloaded counts plus progress and errors', async () => {
  const {dom}=await openOptions({settings:{enabled:true,autoUpdate:false,custom:['politics','personal phrase']},remoteList:{schemaVersion:1,version:'saved',keywords:['mike lee','politics']},downloadedKeywordCount:2,lastUpdate:'2026-11-13T12:00:00Z',updateStatus:'checking',updateError:'Previous failure',granted:true});
  try {
    const text=dom.window.document.getElementById('listInfo').textContent;
    assert.match(text,/Current filters: 40 unique/);assert.match(text,/Permanent political foundation: 38 terms/);assert.match(text,/Downloaded keywords: 2/);
    assert.match(text,/Last successful update:/);assert.match(text,/Automatic updates: Off/);assert.match(text,/Checking for new filters/);assert.match(text,/Last update error: Previous failure/);
  }finally{dom.window.close();}
});

test('a granted installation host needs no runtime request for a manual check; new nondefault sources are rejected',async()=>{
 const c=await openOptions({settings:{enabled:true,autoUpdate:false,source:'',custom:[]},granted:true});
 try{
  c.dom.window.document.getElementById('update').click();await settle();await settle();assert.equal(c.requested.length,0);assert.equal(c.state.remoteList.version,'downloaded-v2');
  c.dom.window.document.getElementById('source').value='https://raw.githubusercontent.com/other/nopartisan/main/keywords/politics.json';
  c.dom.window.document.getElementById('settings').dispatchEvent(new c.dom.window.Event('submit',{cancelable:true}));await settle();
  assert.match(c.dom.window.document.getElementById('status').textContent,/maintained keyword source/);assert.equal(c.state.remoteList.version,'downloaded-v2');
 }finally{c.dom.window.close();}
});
