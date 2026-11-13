const { defaults, validate, sourceURL, UPDATE_PERMISSION } = NOpartisan;
const DAY = 24 * 60 * 60 * 1000;
const RETRY = 60 * 60 * 1000;
let pendingUpdate, foundationPromise;
const effective = stored => ({ ...defaults, ...stored.settings });
const configuredURL = settings => sourceURL(settings.source || defaults.source, settings.source);

async function foundation() {
  if (!foundationPromise) foundationPromise = (async () => {
    const response = await fetch(browser.runtime.getURL('foundational.json'));
    return validate(await response.json());
  })().catch(error => { foundationPromise = undefined; throw error; });
  return foundationPromise;
}
async function schedule() {
  const stored = await browser.storage.local.get(['settings', 'nextUpdate', 'lastUpdate']);
  await browser.alarms.clear('keywords');
  if (!effective(stored).autoUpdate) return;
  const due = stored.nextUpdate || (Date.parse(stored.lastUpdate) + DAY) || Date.now();
  await browser.alarms.create('keywords', { when: Math.max(Date.now() + 60000, due) });
}
async function update({ automatic = false } = {}) {
  if (pendingUpdate) return pendingUpdate;
  pendingUpdate = (async () => {
    try {
      const settings = effective(await browser.storage.local.get('settings'));
      if (automatic && !settings.autoUpdate) return null;
      const url = configuredURL(settings);
      await browser.storage.local.set({ updateStatus: 'checking', lastAttempt: new Date().toISOString() });
      if (!await browser.permissions.contains(UPDATE_PERMISSION)) throw new Error('Keyword update access is missing. Allow access to the update service in Firefox permissions or use Update filters now. Local filtering still works.');
      const response = await fetch(url, { credentials: 'omit', referrerPolicy: 'no-referrer', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error(`Keyword download failed (${response.status}).`);
      const reader = response.body.getReader(); const chunks = []; let size = 0;
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        size += value.length;
        if (size > 1000000) { await reader.cancel(); throw new Error('Keyword download exceeds 1 MB.'); }
        chunks.push(value);
      }
      const bytes = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
      const downloaded = validate(JSON.parse(new TextDecoder().decode(bytes)));
      const permanent = await foundation();
      const list = validate({ ...downloaded, keywords: [...new Set([...downloaded.keywords, ...permanent.keywords])] });
      // Discard obsolete results rather than publishing a response for a changed source.
      const current = effective(await browser.storage.local.get('settings'));
      if (configuredURL(current) !== url) throw new Error('Source changed; try again.');
      if (automatic && !current.autoUpdate) throw new Error('Automatic updates were turned off. Current filters remain active.');
      if (!await browser.permissions.contains(UPDATE_PERMISSION)) throw new Error('Keyword update access was revoked. Current filters remain active.');
      // One storage transaction publishes the complete validated cache and status.
      // Existing content scripts rescan through storage.onChanged.
      await browser.storage.local.set({ remoteList: list, downloadedKeywordCount: downloaded.keywords.length,
        lastUpdate: new Date().toISOString(), updateError: '', updateStatus: 'current', nextUpdate: Date.now() + DAY });
      return list.version;
    } catch (error) {
      await browser.storage.local.set({ updateError: error.message, updateStatus: 'error', nextUpdate: Date.now() + RETRY });
      throw error;
    }
  })();
  try { return await pendingUpdate; }
  finally { pendingUpdate = undefined; await schedule(); }
}
async function automaticUpdate() {
  if (!effective(await browser.storage.local.get('settings')).autoUpdate) return;
  try { await update({ automatic: true }); } catch { /* update records failure; filtering uses local data. */ }
}
async function resume() {
  const stored = await browser.storage.local.get(['settings', 'nextUpdate', 'lastUpdate']);
  await schedule();
  if (!effective(stored).autoUpdate) return;
  const due = stored.nextUpdate || (Date.parse(stored.lastUpdate) + DAY) || 0;
  if (due <= Date.now()) await automaticUpdate();
}
browser.runtime.onInstalled.addListener(async details => {
  const stored = await browser.storage.local.get(null);
  const fresh = details.reason === 'install' && Object.keys(stored).length === 0;
  if (fresh) await browser.storage.local.set({ settings: { ...defaults, autoUpdate: true } });
  else if (!stored.settings) await browser.storage.local.set({ settings: { ...defaults } });
  // No settings, keywords or prior opt-outs are rewritten on upgrade.
  if (fresh) browser.runtime.openOptionsPage().catch(() => {});
  await resume();
});
browser.runtime.onStartup.addListener(resume);
browser.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.settings) resume().catch(() => {});
});
browser.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'keywords') return automaticUpdate(); });
browser.permissions.onAdded.addListener(permissions => {
  if (permissions.origins?.some(origin => origin.startsWith('https://raw.githubusercontent.com/'))) return automaticUpdate();
});
browser.runtime.onMessage.addListener((message, sender) => {
  if (sender.id !== browser.runtime.id || sender.url !== browser.runtime.getURL('options.html')) return;
  if (message.type === 'update') return update().then(version => ({ version }), error => ({ error: error.message }));
});

// User-initiated post inspection. Reports never leave the browser or go to disk storage.
const inspectionMenu = 'nopartisan-why-visible';
async function registerInspectionMenu() {
  await browser.menus.remove(inspectionMenu).catch(() => {});
  browser.menus.create({ id: inspectionMenu, title: 'NOpartisan: Why is this post visible?',
    contexts: ['all'], documentUrlPatterns: ['https://x.com/*'] });
}
browser.runtime.onInstalled.addListener(registerInspectionMenu);
browser.runtime.onStartup.addListener(registerInspectionMenu);
browser.menus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== inspectionMenu || !Number.isInteger(tab?.id)) return;
  let report;
  try {
    report = await browser.tabs.sendMessage(tab.id, { type: 'inspectPost', targetElementId: info.targetElementId }, { frameId: info.frameId ?? 0 });
  } catch {
    report = { error: 'Content script not running or unavailable. Check X website access, reload NOpartisan and refresh the X tab, then try again.' };
  }
  const id = crypto.randomUUID();
  // Separate keys prevent one inspection from consuming another's report.
  await browser.storage.session.set({ [`postInspection:${id}`]: report || { error: 'The content script returned no report. Refresh X and try again.' } });
  await browser.tabs.create({ url: browser.runtime.getURL(`inspection.html#${id}`) });
});
