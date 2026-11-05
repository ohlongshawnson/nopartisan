const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const settle = () => new Promise(resolve => setTimeout(resolve, 20));
test('older settings keep placeholders; opting out persists and reloads correctly', async () => {
  let stored = { enabled: true, custom: ['Mike Lee'], source: '', autoUpdate: false };
  async function open() {
    const dom = new JSDOM(fs.readFileSync('extension/options.html', 'utf8'), { runScripts: 'outside-only' });
    dom.window.browser = {
      storage: { local: { get: async () => ({ settings: stored }), set: async value => { stored = value.settings; } } },
      permissions: { remove: async () => true }
    };
    for (const file of ['core.js', 'options.js']) dom.window.eval(fs.readFileSync(`extension/${file}`, 'utf8'));
    await settle(); return dom;
  }
  let dom = await open();
  try {
    const doc = dom.window.document;
    assert.equal(doc.getElementById('showPlaceholders').checked, true);
    doc.getElementById('showPlaceholders').checked = false;
    doc.getElementById('settings').dispatchEvent(new dom.window.Event('submit', { cancelable: true }));
    await settle();
    assert.equal(doc.getElementById('status').textContent, 'Settings saved.');
    assert.equal(stored.showPlaceholders, false);
    assert.deepEqual(Array.from(stored.custom), ['Mike Lee']);
    dom.window.close(); dom = await open();
    assert.equal(dom.window.document.getElementById('showPlaceholders').checked, false);
  } finally { dom.window.close(); }
});
