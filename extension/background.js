const { defaults, validate, sourceURL } = NOpartisan;
let pendingUpdate;
async function update() {
  if (pendingUpdate) return pendingUpdate;
  pendingUpdate = (async () => {
    const { settings = defaults } = await browser.storage.local.get('settings');
    const url = sourceURL(settings.source || defaults.source);
    if (!await browser.permissions.contains({ origins: ['https://raw.githubusercontent.com/*'] })) throw new Error('Grant GitHub access in settings first.');
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
    const list = validate(JSON.parse(new TextDecoder().decode(bytes)));
    // A source changed while fetching must never publish an obsolete result.
    const current = await browser.storage.local.get('settings');
    if (current.settings?.source !== settings.source) throw new Error('Source changed; try again.');
    await browser.storage.local.set({ remoteList: list, lastUpdate: new Date().toISOString(), updateError: '' });
    return list.version;
  })();
  try { return await pendingUpdate; } finally { pendingUpdate = undefined; }
}
async function schedule() {
  const { settings = defaults } = await browser.storage.local.get('settings');
  await browser.alarms.clear('keywords');
  if (settings.autoUpdate) browser.alarms.create('keywords', { delayInMinutes: 1, periodInMinutes: 1440 });
}
browser.runtime.onInstalled.addListener(async details => {
  await schedule();
  if (details.reason === 'install') return browser.runtime.openOptionsPage();
});
browser.runtime.onStartup.addListener(schedule);
browser.storage.onChanged.addListener((changes, area) => { if (area === 'local' && changes.settings) schedule(); });
browser.alarms.onAlarm.addListener(async alarm => {
  if (alarm.name !== 'keywords') return;
  try { await update(); } catch (error) { await browser.storage.local.set({ updateError: error.message }); }
});
browser.runtime.onMessage.addListener((message, sender) => {
  if (sender.id !== browser.runtime.id || sender.url !== browser.runtime.getURL('options.html')) return;
  if (message.type === 'update') return update().then(version => ({ version }), async error => {
    await browser.storage.local.set({ updateError: error.message });
    return { error: error.message };
  });
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
