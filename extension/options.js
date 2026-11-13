const $ = id => document.getElementById(id);
const GITHUB_PERMISSION = { origins: ['https://raw.githubusercontent.com/*'] };
let bundledList, foundationalList;
let saving = false;

async function loadSiteAccess() {
  const rows = await Promise.all(Object.entries(NOpartisan.sites).map(async ([name, origin]) => {
    const granted = await browser.permissions.contains({ origins: [origin] });
    const row = document.createElement('p');
    row.append(`${name}: ${granted ? 'Access granted.' : 'Access missing; filtering cannot run.'} `);
    if (!granted) {
      const button = document.createElement('button');
      button.type = 'button'; button.textContent = `Grant ${name} access`;
      button.addEventListener('click', async () => {
        // Request only the selected, already-declared website, directly from a user gesture.
        try {
          const allowed = await browser.permissions.request({ origins: [origin] });
          $('status').textContent = allowed ? `${name} access granted. Refresh your ${name} tabs to start filtering.` : `${name} access was declined. Filtering cannot run on this site.`;
          await loadSiteAccess();
        } catch (error) { $('status').textContent = error.message; }
      });
      row.append(button);
    }
    return row;
  }));
  $('siteAccess').replaceChildren(...rows);
}
browser.permissions.onAdded.addListener(() => loadSiteAccess().catch(error => { $('status').textContent = error.message; }));
browser.permissions.onRemoved.addListener(() => loadSiteAccess().catch(error => { $('status').textContent = error.message; }));
loadSiteAccess().catch(error => { $('status').textContent = error.message; });

async function load(refreshControls = true) {
  const [stored, granted, bundled, foundational] = await Promise.all([
    browser.storage.local.get(['settings', 'remoteList', 'lastUpdate', 'updateError']),
    browser.permissions.contains(GITHUB_PERMISSION),
    (async () => {
      if (!bundledList) bundledList = NOpartisan.validate(await (await fetch(browser.runtime.getURL('keywords.json'))).json());
      return bundledList;
    })(),
    (async () => {
      if (!foundationalList) foundationalList = NOpartisan.validate(await (await fetch(browser.runtime.getURL('foundational.json'))).json());
      return foundationalList;
    })()
  ]);
  const settings = { ...NOpartisan.defaults, ...stored.settings };
  const activeList = stored.remoteList ? NOpartisan.validate(stored.remoteList) : bundled;
  if (refreshControls) {
    $('enabled').checked = settings.enabled;
    $('showPlaceholders').checked = settings.showPlaceholders !== false;
    $('custom').value = (settings.custom || []).join('\n');
    $('source').value = settings.source || NOpartisan.DEFAULT_SOURCE;
    $('autoUpdate').checked = Boolean(settings.autoUpdate);
  }
  $('save').disabled = false;
  $('update').disabled = false;
  const listSource = stored.remoteList ? 'downloaded' : 'bundled';
  const personalCount = new Set((settings.custom || []).map(NOpartisan.normalize).filter(Boolean)).size;
  const lines = [`Active list: ${listSource}, version ${activeList.version}, ${activeList.keywords.length.toLocaleString()} unique keywords.`];
  lines.push(`${foundational.keywords.length} permanent foundational terms supplement the active list, including downloaded lists.`);
  if (personalCount) lines.push(`${personalCount.toLocaleString()} personal keywords are also active.`);
  lines.push(stored.lastUpdate ? `Last successful download: ${new Date(stored.lastUpdate).toLocaleString()}.` : 'Last successful download: None; the bundled list is ready offline.');
  if (stored.updateError) lines.push(`Latest update failed: ${stored.updateError} The previous valid list remains active.`);
  else if (settings.autoUpdate && granted) lines.push('Daily updates are on while Firefox is running.');
  else if (settings.autoUpdate) lines.push('Daily updates are enabled, but GitHub access is not currently granted. Choose Update filters now to request access.');
  else lines.push('Automatic updates are off.');
  $('listInfo').textContent = lines.join(' ');
}

async function persistSettings({ askForUpdates = false } = {}) {
  const requestedAutoUpdate = $('autoUpdate').checked;
  const sourceInput = $('source').value.trim();
  const source = sourceInput ? NOpartisan.sourceURL(sourceInput) : NOpartisan.DEFAULT_SOURCE;
  const custom = $('custom').value.split('\n').map(value => value.trim()).filter(Boolean);
  if (custom.length) NOpartisan.validate({ schemaVersion: 1, version: 'personal', keywords: custom });
  // Request permission before the first await so Firefox sees this as a direct user action.
  const permissionRequest = requestedAutoUpdate || askForUpdates
    ? browser.permissions.request(GITHUB_PERMISSION)
    : Promise.resolve(true);
  const granted = await permissionRequest;
  const { settings: old = {} } = await browser.storage.local.get('settings');
  const oldSource = old.source || NOpartisan.DEFAULT_SOURCE;
  const autoUpdate = requestedAutoUpdate && granted;
  if (oldSource !== source) await browser.storage.local.remove(['remoteList', 'lastUpdate', 'updateError']);
  await browser.storage.local.set({ settings: {
    ...NOpartisan.defaults, ...old,
    enabled: $('enabled').checked,
    showPlaceholders: $('showPlaceholders').checked,
    custom, source, autoUpdate
  } });
  if (requestedAutoUpdate && !granted) $('autoUpdate').checked = false;
  await load();
  return { granted, requestedAutoUpdate };
}

$('settings').addEventListener('submit', async event => {
  event.preventDefault();
  if (saving) return;
  saving = true; $('save').disabled = true; $('update').disabled = true;
  try {
    const result = await persistSettings();
    $('status').textContent = result.requestedAutoUpdate && !result.granted
      ? 'GitHub access was declined. Filtering remains on; you can enable updates later.'
      : 'Settings saved.';
  } catch (error) { $('status').textContent = error.message; }
  finally { saving = false; $('save').disabled = false; $('update').disabled = false; }
});

$('update').addEventListener('click', async () => {
  if (saving) return;
  saving = true; $('save').disabled = true; $('update').disabled = true;
  $('status').textContent = 'Connecting to GitHub…';
  try {
    const result = await persistSettings({ askForUpdates: true });
    if (!result.granted) throw new Error('GitHub access was declined. Filtering remains available with the current list.');
    $('status').textContent = 'Downloading the latest political filters…';
    const response = await browser.runtime.sendMessage({ type: 'update' });
    if (response.error) throw new Error(response.error);
    await load();
    $('status').textContent = `Updated to keyword list ${response.version}.`;
  } catch (error) { $('status').textContent = error.message; await load().catch(() => {}); }
  finally { saving = false; $('save').disabled = false; $('update').disabled = false; }
});

browser.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && (changes.settings || changes.remoteList || changes.lastUpdate || changes.updateError)) {
    load(Boolean(changes.settings)).catch(error => { $('status').textContent = error.message; });
  }
});
load().catch(error => { $('status').textContent = error.message; });
