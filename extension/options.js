const $ = id => document.getElementById(id);
async function load() {
  const { settings = NOpartisan.defaults, remoteList, lastUpdate, updateError } = await browser.storage.local.get(['settings', 'remoteList', 'lastUpdate', 'updateError']);
  $('showPlaceholders').checked = settings.showPlaceholders !== false;
  $('enabled').checked = settings.enabled; $('custom').value = settings.custom.join('\n');
  $('source').value = settings.source; $('autoUpdate').checked = settings.autoUpdate;
  $('listInfo').textContent = remoteList ? `Downloaded list: ${remoteList.version}. Last success: ${lastUpdate}. ${updateError || ''}` : 'Using bundled starter keywords.';
  $('save').disabled = false; $('update').disabled = false;
}
$('settings').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const source = $('source').value.trim();
    if (source) NOpartisan.sourceURL(source);
    const custom = $('custom').value.split('\n').map(s => s.trim()).filter(Boolean);
    if (custom.length) NOpartisan.validate({ schemaVersion: 1, version: 'custom', keywords: custom });
    if (source && !await browser.permissions.request({ origins: ['https://raw.githubusercontent.com/*'] })) throw new Error('GitHub access was not granted.');
    const { settings: old = NOpartisan.defaults } = await browser.storage.local.get('settings');
    if (old.source !== source) await browser.storage.local.remove(['remoteList', 'lastUpdate', 'updateError']);
    await browser.storage.local.set({ settings: { enabled: $('enabled').checked, showPlaceholders: $('showPlaceholders').checked, custom, source, autoUpdate: Boolean(source && $('autoUpdate').checked) } });
    if (!source) await browser.permissions.remove({ origins: ['https://raw.githubusercontent.com/*'] });
    await load(); $('status').textContent = 'Settings saved.';
  } catch (error) { $('status').textContent = error.message; }
});
$('update').addEventListener('click', async () => {
  $('update').disabled = true; $('status').textContent = 'Downloading saved source…';
  try {
    const result = await browser.runtime.sendMessage({ type: 'update' });
    if (result.error) throw new Error(result.error);
    await load(); $('status').textContent = `Loaded keyword version ${result.version}.`;
  } catch (error) { $('status').textContent = error.message; }
  finally { $('update').disabled = false; }
});
load().catch(error => { $('status').textContent = error.message; });
