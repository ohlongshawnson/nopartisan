const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const published = JSON.parse(fs.readFileSync('keywords/politics.json', 'utf8'));
async function waitFor(check) {
  const deadline = Date.now() + 8000;
  while (!check()) { if (Date.now() > deadline) throw new Error('Timed out waiting for scan'); await new Promise(resolve => setTimeout(resolve, 30)); }
}
async function setup() {
  const dom = new JSDOM(fs.readFileSync('tests/fixtures/x-missed-posts.html', 'utf8'), { url: 'https://x.com/home', runScripts: 'outside-only' });
  const w = dom.window, logs = [], errors = [];
  let listener, changed, target;
  const stored = { settings: { enabled: true, showPlaceholders: true, custom: [], source: 'https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json' }, remoteList: published, lastUpdate: '2026-11-05T18:51:21.317Z' };
  w.console.info = (...args) => logs.push(args); w.console.error = (...args) => errors.push(args);
  w.browser = { runtime: { id: 'test', getURL: p => p, onMessage: { addListener: fn => { listener = fn; } } },
    menus: { getTargetElement: () => target }, storage: { local: { get: async () => stored }, onChanged: { addListener: fn => { changed = fn; } } } };
  w.fetch = async () => ({ json: async () => JSON.parse(fs.readFileSync('extension/keywords.json', 'utf8')) });
  for (const file of ['core.js', 'x-adapter.js', 'content.js']) w.eval(fs.readFileSync(`extension/${file}`, 'utf8'));
  await waitFor(() => w.NOpartisanDiagnostics.initialized && w.NOpartisanDiagnostics.candidates === 11);
  const $ = id => w.document.getElementById(id);
  return { w, $, logs, errors, stored, hidden: id => $(id).classList.contains('nopartisan-filtered'),
    inspect: async id => { target = $(id); return JSON.parse(JSON.stringify(await listener({ type: 'inspectPost', targetElementId: 1 }, { id: 'test' }))); },
    listener: () => listener, changed: changes => changed(changes, 'local'), close: () => w.close() };
}
test('published-list screenshot fragments are coverage gaps; full names, quotes, authors, and accessible image descriptions match', async () => {
  const ctx = await setup();
  try {
    for (const id of ['rich', 'dustin', 'imageOnly', 'externalLabel', 'unrelated']) assert.equal(ctx.hidden(id), false, id);
    for (const id of ['fullNames', 'quoteFullName', 'unknownQuote', 'authorOnly', 'altOnly', 'accessibleOnly']) assert.equal(ctx.hidden(id), true, id);
    assert.equal(ctx.hidden('timeline'), false); assert.equal(ctx.hidden('sidebar'), false);
    const rich = await ctx.inspect('rich');
    assert.equal(rich.list.version, published.version); assert.equal(rich.list.keywordCount, published.keywords.length);
    assert.equal(rich.list.source, 'downloaded'); assert.equal(rich.recognized, true); assert.equal(rich.matched, false); assert.equal(rich.revealed, false);
    assert.match(rich.extracted.authorText.join(' '), /Rich Neumeister/);
    assert.match(rich.extracted.quotedText.join(' '), /Klobuchar\/Walz/);
    assert.doesNotMatch(rich.extracted.outerText, /Klobuchar|Neumeister/);
    const full = await ctx.inspect('fullNames'); assert.deepEqual(full.matchedKeywords.sort(), ['amy klobuchar', 'tim walz']);
    const image = await ctx.inspect('imageOnly'); assert.deepEqual(image.extracted.imageAltText, ['Image']);
    assert.equal(image.extracted.segments.some(text => text.includes('FOUR WOMEN')), false, 'No OCR or generic attribute scraping');
    assert.equal((await ctx.inspect('timeline')).recognized, false);
    assert.equal((await ctx.inspect('authorOnly')).matched, true);
    assert.equal(ctx.listener()({ type: 'inspectPost' }, { id: 'other-extension' }), undefined);
    const routineLogs = JSON.stringify(ctx.logs);
    for (const text of ['Rich Neumeister', 'Klobuchar/Walz', 'Minneapolis elected', 'Tim Walz at an event']) assert.equal(routineLogs.includes(text), false);
    assert.equal(ctx.errors.length, 0);
  } finally { ctx.close(); }
});
test('alt/ARIA changes, inserted quotes, and recycled same-text cards rescan and reset reveal identity', async () => {
  const ctx = await setup();
  try {
    ctx.$('imageOnly').querySelector('img').alt = 'Amy Klobuchar in a photograph';
    await waitFor(() => ctx.hidden('imageOnly'));
    ctx.$('imageOnly').querySelector('img').alt = 'Image';
    await waitFor(() => !ctx.hidden('imageOnly'));
    ctx.$('accessibleOnly').querySelector('[role="img"]').setAttribute('aria-label', 'A garden');
    await waitFor(() => !ctx.hidden('accessibleOnly'));
    ctx.$('dustin').insertAdjacentHTML('beforeend', '<div role="link"><div data-testid="tweetText">Tim Walz speaks.</div></div>');
    await waitFor(() => ctx.hidden('dustin'));
    ctx.$('fullNames').previousElementSibling.querySelector('button').click();
    await waitFor(() => !ctx.hidden('fullNames'));
    assert.equal((await ctx.inspect('fullNames')).revealed, true);
    ctx.$('fullNames').querySelector('a').href = '/News/status/201';
    await waitFor(() => ctx.hidden('fullNames'));
    assert.equal((await ctx.inspect('fullNames')).revealed, false);
    ctx.$('fullNames').removeAttribute('data-testid');
    await waitFor(() => !ctx.hidden('fullNames'));
    assert.notEqual(ctx.$('fullNames').previousElementSibling?.dataset.nopartisanNotice, 'true');
  } finally { ctx.close(); }
});
test('diagnosis distinguishes an old downloaded list and reflects list updates in open tabs', async () => {
  const ctx = await setup();
  try {
    ctx.stored.remoteList = { schemaVersion: 1, version: 'old-list', keywords: ['MAGA'] };
    const beforeEvent = await ctx.inspect('quoteFullName');
    assert.equal(beforeEvent.list.version, published.version, 'Inspection observes the running matcher without refreshing it');
    assert.equal(beforeEvent.downloadedListInStorage.version, 'old-list');
    assert.equal(beforeEvent.activeListDiffersFromDownloaded, true);
    ctx.changed({ remoteList: {} });
    await waitFor(() => !ctx.hidden('quoteFullName'));
    const old = await ctx.inspect('quoteFullName'); assert.equal(old.list.version, 'old-list'); assert.equal(old.list.keywordCount, 1); assert.equal(old.matched, false);
    ctx.stored.remoteList = published;ctx.changed({ remoteList: {} });
    await waitFor(() => ctx.hidden('quoteFullName'));
    assert.equal((await ctx.inspect('quoteFullName')).list.keywordCount, published.keywords.length);
  } finally { ctx.close(); }
});
