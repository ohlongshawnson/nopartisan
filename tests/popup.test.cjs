const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const settle = () => new Promise(resolve => setTimeout(resolve, 20));
async function setup(initial) {
  const dom = new JSDOM(fs.readFileSync('extension/popup.html', 'utf8'), { runScripts: 'outside-only' });
  const w = dom.window;
  let settings = initial, listener, optionsOpened = false, closed = false, failSave = false;
  const closeWindow = w.close.bind(w);
  w.close = () => { closed = true; };
  w.browser = {
    storage: {
      local: { get: async () => ({ settings }), set: async data => {
        if (failSave) throw new Error('Storage unavailable');
        settings = data.settings; listener({ settings: { newValue: settings } }, 'local');
      } },
      onChanged: { addListener: callback => { listener = callback; } }
    },
    runtime: { openOptionsPage: async () => { optionsOpened = true; } }
  };
  for (const file of ['core.js', 'popup.js']) w.eval(fs.readFileSync(`extension/${file}`, 'utf8'));
  await settle();
  return { w, settings: () => settings, close: closeWindow,
    change: async (id, value) => { const input = w.document.getElementById(id); input.checked = value; input.dispatchEvent(new w.Event('change')); await settle(); },
    external: async value => { settings = value; listener({ settings: { newValue: value } }, 'local'); await settle(); },
    fail: () => { failSave = true; }, optionsOpened: () => optionsOpened, closed: () => closed,
  };
}
test('popup defaults and quick toggles preserve keywords and update preferences', async () => {
  const original = { enabled: true, custom: ['Mike Lee'], source: 'https://raw.githubusercontent.com/owner/nopartisan/main/keywords/politics.json', autoUpdate: true };
  const ctx = await setup(original); const $ = id => ctx.w.document.getElementById(id);
  assert.equal($('showPlaceholders').checked, true);
  await ctx.change('enabled', false);
  assert.equal(ctx.settings().enabled, false);
  assert.deepEqual(ctx.settings().custom, original.custom);
  assert.equal(ctx.settings().source, original.source); assert.equal(ctx.settings().autoUpdate, true);
  assert.match($('status').textContent, /paused/);
  await ctx.change('showPlaceholders', false);
  assert.equal(ctx.settings().showPlaceholders, false); assert.equal(ctx.settings().enabled, false);
  await ctx.external({ ...original, showPlaceholders: true });
  assert.equal($('enabled').checked, true); assert.equal($('showPlaceholders').checked, true);
  assert.equal($('enabled').disabled, false);
  ctx.close();
});
test('popup restores saved toggle on failure and opens full settings', async () => {
  const ctx = await setup({ enabled: true }); const $ = id => ctx.w.document.getElementById(id);
  ctx.fail(); await ctx.change('enabled', false);
  assert.equal($('enabled').checked, true); assert.equal($('enabled').disabled, false);
  assert.match($('status').textContent, /Could not save: Storage unavailable/);
  $('settings').click(); await settle();
  assert.equal(ctx.optionsOpened(), true); assert.equal(ctx.closed(), true);
  ctx.close();
});
test('toolbar action declares the popup', () => {
  const manifest = JSON.parse(fs.readFileSync('extension/manifest.json', 'utf8'));
  assert.equal(manifest.action.default_popup, 'popup.html');
});
