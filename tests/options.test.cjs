const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const settle = () => new Promise(resolve => setTimeout(resolve, 40));
const bundle = JSON.parse(fs.readFileSync('extension/keywords.json', 'utf8'));

async function openOptions({ settings, remoteList, granted = false, allow = true, lastUpdate, updateError } = {}) {
  const state = { settings, remoteList, lastUpdate, updateError };
  const changes = [];
  const requested = [];
  const dom = new JSDOM(fs.readFileSync('extension/options.html', 'utf8'), { runScripts: 'outside-only', url: 'moz-extension://test/options.html' });
  const w = dom.window;
  w.fetch = async () => ({ json: async () => bundle });
  w.browser = {
    storage: { local: {
      get: async keys => {
        if (!keys) return state;
        return Object.fromEntries((Array.isArray(keys) ? keys : [keys]).filter(key => key in state).map(key => [key, state[key]]));
      },
      set: async value => Object.assign(state, value),
      remove: async keys => keys.forEach(key => delete state[key])
    }, onChanged: { addListener: fn => changes.push(fn) } },
    permissions: { contains: async () => granted, request: async value => { requested.push(value); granted = allow; return allow; } },
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

test('fresh setup reports the complete bundled list and does not request GitHub access', async () => {
  const { dom, requested } = await openOptions();
  try {
    const doc = dom.window.document;
    assert.equal(doc.getElementById('enabled').checked, true);
    assert.equal(doc.getElementById('autoUpdate').checked, false);
    assert.equal(doc.getElementById('source').value, 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json');
    assert.match(doc.getElementById('listInfo').textContent, new RegExp(`bundled, version ${bundle.version}, ${bundle.keywords.length} unique keywords`));
    assert.match(doc.getElementById('listInfo').textContent, /1 contextual rule active/);
    assert.match(doc.getElementById('rules').value, /^Trump => politics, political, president/);
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
    assert.match(doc.getElementById('listInfo').textContent, /downloaded, version cached, 1 unique keywords/);
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(state.settings.enabled, false);
    assert.equal(state.settings.autoUpdate, false);
    assert.deepEqual(Array.from(state.settings.custom), ['Mike Lee']);
    assert.equal(state.settings.source, saved.source);
    assert.equal(state.remoteList.version, 'cached');
  } finally { dom.window.close(); }
});

test('editing contextual rules saves locally; invalid rules keep the last valid settings', async () => {
  const { dom, state, requested } = await openOptions();
  try {
    const doc = dom.window.document;
    const rules = doc.getElementById('rules');
    rules.value = 'Trump => election, deportation\nvote => blue, red';
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(state.settings.rules.length, 2);
    assert.equal(state.settings.rules[1].all[0], 'vote');
    assert.deepEqual(requested, []);
    rules.value = 'Trump =>';
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(state.settings.rules.length, 2);
    assert.match(doc.getElementById('status').textContent, /Invalid term/);
    rules.value = '';
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.deepEqual(Array.from(state.settings.rules), []);
  } finally { dom.window.close(); }
});
test('invalid saved rules can be repaired without losing older preferences', async () => {
  const saved = { enabled: false, showPlaceholders: false, custom: ['Mike Lee'], rules: [{ all: ['Trump'], any: [] }], source: 'https://raw.githubusercontent.com/team/nopartisan/main/custom.json', autoUpdate: false };
  const { dom, state } = await openOptions({ settings: saved });
  try {
    const doc = dom.window.document;
    assert.match(doc.getElementById('listInfo').textContent, /Saved contextual rules are invalid/);
    assert.equal(doc.getElementById('rules').value, '');
    doc.getElementById('rules').value = 'Trump => election';
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(state.settings.enabled, false);
    assert.equal(state.settings.showPlaceholders, false);
    assert.deepEqual(Array.from(state.settings.custom), ['Mike Lee']);
    assert.equal(state.settings.source, saved.source);
    assert.equal(state.settings.autoUpdate, false);
    assert.equal(state.settings.rules[0].any[0], 'election');
  } finally { dom.window.close(); }
});

test('daily updates require optional permission; denial keeps filtering usable', async () => {
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
    assert.match(dom.window.document.getElementById('listInfo').textContent, /downloaded, version downloaded-v2, 1 unique keywords/);
    assert.match(dom.window.document.getElementById('listInfo').textContent, /Last successful download:/);
  } finally { dom.window.close(); }
});

test('failed download status keeps the last valid list visible', async () => {
  const { dom } = await openOptions({
    remoteList: { schemaVersion: 1, version: 'last-good', keywords: ['one phrase'] },
    lastUpdate: '2026-11-05T18:51:21.317Z', updateError: 'Network unavailable.'
  });
  try {
    const info = dom.window.document.getElementById('listInfo').textContent;
    assert.match(info, /downloaded, version last-good, 1 unique keywords/);
    assert.match(info, /Last successful download:/);
    assert.match(info, /Latest update failed: Network unavailable. The previous valid list remains active/);
  } finally { dom.window.close(); }
});
