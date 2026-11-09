const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const wait = () => new Promise(resolve => setTimeout(resolve, 160));
async function setup({ custom = ['Mike Lee', 'Republicans', 'mike lee'], failFetch = false } = {}) {
  const dom = new JSDOM(fs.readFileSync('tests/fixtures/x-feed.html', 'utf8'), { url: 'https://x.com/search?q=Mike%20Lee', runScripts: 'outside-only' });
  const w = dom.window; let listener; const logs = [], errors = [];
  let settings = { enabled: true, custom };
  w.console.info = (...args) => logs.push(args); w.console.error = (...args) => errors.push(args);
  w.browser = { runtime: { id: 'test', onMessage: { addListener() {} }, getURL: p => `moz-extension://test/${p}` }, storage: { local: { get: async () => ({ settings }) }, onChanged: { addListener: f => { listener = f; } } } };
  w.fetch = async () => { if (failFetch) throw new TypeError('NetworkError when attempting to fetch resource.'); return { json: async () => JSON.parse(fs.readFileSync('tests/fixtures/starter-keywords.json', 'utf8')) }; };
  w.eval(fs.readFileSync('extension/core.js', 'utf8')); w.eval(fs.readFileSync('extension/x-adapter.js','utf8')); w.eval(fs.readFileSync('extension/content.js', 'utf8'));
  await wait();
  return { w, logs, errors, close: () => w.close(), save: async update => { settings = { ...settings, ...update }; listener({ settings: { newValue: settings } }, 'local'); await wait(); } };
}
const hidden = (w, id) => w.document.getElementById(id).classList.contains('nopartisan-filtered');
test('Mike Lee: exact phrase, mixed case, author, quoted content, duplicate keywords, and individual trends', async () => {
  const ctx = await setup(); const { w } = ctx;
  try {
    for (const id of ['exact', 'case', 'author', 'quote', 'nestedQuote', 'blockedTrend']) assert.equal(hidden(w, id), true, id);
    for (const id of ['neutral', 'neutralTrend', 'timeline', 'sidebar', 'search']) assert.equal(hidden(w, id), false, id);
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 6);
    assert.equal(w.document.querySelector('#nestedQuote article').classList.contains('nopartisan-filtered'), false);
    assert.deepEqual(JSON.parse(JSON.stringify(w.NOpartisanDiagnostics)), { build: 'post-inspection-1', initialized: true, enabled: true, keywordCount: 12, candidates: 8, matched: 6, hidden: 6, runtimeErrors: 0 });
    assert.equal(ctx.errors.length, 0);
  } finally { ctx.close(); }
});
test('saving and removing personal keywords rescans an already-open page', async () => {
  const ctx = await setup({ custom: [] });
  try {
    assert.equal(hidden(ctx.w, 'exact'), false);
    await ctx.save({ custom: ['Mike Lee', 'mike lee'] });
    assert.equal(hidden(ctx.w, 'exact'), true); assert.equal(hidden(ctx.w, 'blockedTrend'), true);
    await ctx.save({ custom: [] });
    assert.equal(hidden(ctx.w, 'exact'), false); assert.equal(hidden(ctx.w, 'blockedTrend'), false);
    assert.equal(ctx.w.document.querySelectorAll('.nopartisan-notice').length, 0);
  } finally { ctx.close(); }
});
test('editing contextual rules rescans an already-open X page', async () => {
  const ctx = await setup({ custom: [] });
  try {
    assert.equal(hidden(ctx.w, 'neutral'), false);
    await ctx.save({ rules: ctx.w.NOpartisan.parseRules('garden => magazine') });
    assert.equal(hidden(ctx.w, 'neutral'), true);
    await ctx.save({ rules: [] });
    assert.equal(hidden(ctx.w, 'neutral'), false);
  } finally { ctx.close(); }
});
test('appended posts and trends filter; disabling restores every hidden element', async () => {
  const ctx = await setup(); const { w } = ctx;
  try {
    w.document.querySelector('#timeline').insertAdjacentHTML('beforeend', '<article id="newPost" data-testid="tweet">Mike Lee news</article>');
    w.document.querySelector('#sidebar').insertAdjacentHTML('beforeend', '<div id="newTrend" data-testid="trend">MIKE LEE</div>');
    await wait(); assert.equal(hidden(w, 'newPost'), true); assert.equal(hidden(w, 'newTrend'), true);
    await ctx.save({ enabled: false });
    assert.equal(w.document.querySelectorAll('.nopartisan-filtered').length, 0);
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 0);
  } finally { ctx.close(); }
});
test('Reveal works for a post and an individual trend and survives rescanning', async () => {
  const ctx = await setup(); const { w } = ctx;
  try {
    for (const id of ['exact', 'blockedTrend']) {
      w.document.getElementById(id).previousElementSibling.querySelector('button').click();
      await wait(); assert.equal(hidden(w, id), false);
    }
    await ctx.save({ custom: ['Mike Lee'] }); assert.equal(hidden(w, 'exact'), false); assert.equal(hidden(w, 'blockedTrend'), false);
    w.document.getElementById('exact').textContent = 'A different Mike Lee report';
    await wait(); assert.equal(hidden(w, 'exact'), true);
  } finally { ctx.close(); }
});
test('initialization failure emits a diagnostic instead of silently rejecting', async () => {
  const ctx = await setup({ failFetch: true });
  try {
    assert.equal(ctx.w.NOpartisanDiagnostics.initialized, false);
    assert.equal(ctx.w.NOpartisanDiagnostics.runtimeErrors, 1);
    assert.match(ctx.errors[0][0], /NOpartisan/);
  } finally { ctx.close(); }
});
test('manifest makes the fetched bundled list accessible on every supported origin', () => {
  const manifest = JSON.parse(fs.readFileSync('extension/manifest.json', 'utf8'));
  const entry = manifest.web_accessible_resources.find(entry => entry.resources.includes('keywords.json'));
  assert.ok(entry, 'Firefox MV3 blocks the packaged-file fetch without this declaration');
  assert.deepEqual(entry.matches, manifest.content_scripts[0].matches);
  assert.deepEqual(entry.resources, ['keywords.json']);
  assert.deepEqual(manifest.content_scripts[0].js, ['core.js', 'x-adapter.js', 'content.js']);
  assert.ok(manifest.host_permissions.includes('https://x.com/*'));
});

test('placeholder preference updates existing posts and trends and handles new candidates', async () => {
  const ctx = await setup(); const { w } = ctx;
  try {
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 6);
    await ctx.save({ showPlaceholders: false });
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 0);
    for (const id of ['exact', 'blockedTrend']) assert.equal(hidden(w, id), true);
    w.document.querySelector('#timeline').insertAdjacentHTML('beforeend', '<article id="newPost" data-testid="tweet">Mike Lee news</article>');
    await wait(); assert.equal(hidden(w, 'newPost'), true);
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 0);
    await ctx.save({ showPlaceholders: true });
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 7);
    w.document.getElementById('exact').previousElementSibling.querySelector('button').click();
    await wait(); assert.equal(hidden(w, 'exact'), false);
    await ctx.save({ showPlaceholders: false, enabled: false });
    assert.equal(w.document.querySelectorAll('.nopartisan-filtered').length, 0);
    assert.equal(w.document.querySelectorAll('.nopartisan-notice').length, 0);
  } finally { ctx.close(); }
});
