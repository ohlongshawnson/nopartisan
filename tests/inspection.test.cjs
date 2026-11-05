const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const pause = () => new Promise(resolve => setTimeout(resolve, 30));
test('context menu requests only the selected frame; post report goes only to session memory and a local URL', async () => {
  let clicked, request, created, registration; const installed = [], session = {};
  const report = { recognized: true, extracted: { outerText: 'PRIVATE_POST_SENTINEL' } };
  const browser = {
    runtime: { id: 'test', getURL: path => `moz-extension://test/${path}`, onInstalled: { addListener: fn => installed.push(fn) }, onStartup: { addListener() {} }, onMessage: { addListener() {} } },
    menus: { remove: async () => {}, create: data => { registration = data; }, onClicked: { addListener: fn => { clicked = fn; } } },
    storage: { local: { get: async () => { throw new Error('Diagnostic should not read or write local disk storage'); } }, session: { set: async value => Object.assign(session, value) }, onChanged: { addListener() {} } },
    alarms: { onAlarm: { addListener() {} } },
    tabs: { sendMessage: async (...args) => { request = args; return report; }, create: async value => { created = value; } }
  };
  const context = vm.createContext({ browser, crypto: { randomUUID: () => 'unique-report' } });
  vm.runInContext(fs.readFileSync('extension/core.js', 'utf8'), context);
  vm.runInContext(fs.readFileSync('extension/background.js', 'utf8'), context);
  await installed[1]();
  assert.equal(registration.id, 'nopartisan-why-visible'); assert.equal(registration.documentUrlPatterns[0], 'https://x.com/*');
  await clicked({ menuItemId: 'nopartisan-why-visible', targetElementId: 42, frameId: 7 }, { id: 9 });
  assert.equal(request[0], 9); assert.equal(request[1].targetElementId, 42); assert.equal(request[2].frameId, 7);
  assert.equal(session['postInspection:unique-report'], report);
  assert.equal(created.url, 'moz-extension://test/inspection.html#unique-report');
  assert.equal(created.url.includes('PRIVATE_POST_SENTINEL'), false);
});
test('inspection page consumes only its own report and renders hostile text as text', async () => {
  const dom = new JSDOM(fs.readFileSync('extension/inspection.html', 'utf8'), { url: 'https://extension.invalid/inspection.html#one', runScripts: 'outside-only' });
  const malicious = '<img src="https://example.invalid/should-never-load" onerror="window.compromised=true">';
  const session = { 'postInspection:one': { initialized: true, recognized: true, filteringEnabled: true, matched: false, revealed: false,
    list: { version: 'v', keywordCount: 869 }, extracted: { outerText: malicious, authorText: ['An author'], quotedText: ['Klobuchar/Walz'], imageAltText: ['Image'], accessibleImageText: [] } },
    'postInspection:two': { another: true } };
  dom.window.browser = { storage: { session: { get: async key => ({ [key]: session[key] }), remove: async key => { delete session[key]; } } } };
  try {
    dom.window.eval(fs.readFileSync('extension/inspection.js', 'utf8')); await pause();
    const doc = dom.window.document;
    assert.equal(doc.getElementById('outer').textContent, malicious);
    assert.equal(doc.querySelectorAll('img').length, 0);
    assert.equal(doc.getElementById('quote').textContent, 'Klobuchar/Walz');
    assert.match(doc.getElementById('state').textContent, /869/);
    assert.match(doc.getElementById('summary').textContent, /No active keyword/);
    assert.equal(session['postInspection:one'], undefined);assert.ok(session['postInspection:two']);
    assert.equal(dom.window.compromised, undefined);
  } finally { dom.window.close(); }
});
