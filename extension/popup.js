const $ = id => document.getElementById(id);
const toggles = ['enabled', 'showPlaceholders'];
let saving = false;
function setDisabled(disabled) { toggles.forEach(key => { $(key).disabled = disabled; }); }
async function load() {
  const { settings = {} } = await browser.storage.local.get('settings');
  const active = { ...NOpartisan.defaults, ...settings };
  toggles.forEach(key => { $(key).checked = active[key] !== false; });
  $('status').textContent = active.enabled ? 'Filtering is on across supported sites.' : 'Filtering is paused across supported sites.';
  setDisabled(saving);
}
async function save(key, value) {
  if (saving) return;
  saving = true;
  setDisabled(true);
  try {
    // Read current settings so a quick toggle preserves keywords and update preferences.
    const { settings = {} } = await browser.storage.local.get('settings');
    await browser.storage.local.set({ settings: { ...NOpartisan.defaults, ...settings, [key]: value } });
    await load();
  } catch (error) {
    try { await load(); } catch { /* Keep the save error visible. */ }
    $('status').textContent = `Could not save: ${error.message}`;
  } finally {
    saving = false;
    setDisabled(false);
  }
}
toggles.forEach(key => { $(key).addEventListener('change', () => save(key, $(key).checked)); });
$('settings').addEventListener('click', async () => {
  try { await browser.runtime.openOptionsPage(); window.close(); }
  catch (error) { $('status').textContent = `Could not open settings: ${error.message}`; }
});
browser.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.settings) load().catch(error => { $('status').textContent = error.message; });
});
load().catch(error => { $('status').textContent = `Could not load settings: ${error.message}`; });
