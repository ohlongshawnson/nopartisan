// Local diagnostics contain counts only, never feed text or matched phrases.
const diagnostics = globalThis.NOpartisanDiagnostics = {
  build: 'hide-placeholder-1', initialized: false, enabled: null,
  keywordCount: 0, candidates: 0, matched: 0, hidden: 0, runtimeErrors: 0
};
function reportError(error) {
  diagnostics.runtimeErrors++;
  console.error('[NOpartisan] content script error', error);
}
console.info('[NOpartisan] content script started', diagnostics.build);
(async () => {
  const selectors = { 'www.reddit.com': 'shreddit-post, div[data-testid="post-container"]', 'x.com': 'article[data-testid="tweet"], [data-testid="trend"]', 'www.facebook.com': '[role="feed"] [role="article"]' };
  const selector = selectors[location.hostname];
  if (!selector) return;
  const bundled = NOpartisan.validate(await (await fetch(browser.runtime.getURL('keywords.json'))).json());
  let enabled = true, showPlaceholders = true, matches = () => false, queued = false;
  const revealed = new WeakMap();
  let previousSummary;
  // textContent joins adjacent block labels (e.g. "PoliticsMike Lee1,000 posts").
  // Preserve their rendered boundaries even while our CSS hides the candidate.
  // innerText alone falls back to textContent on display:none elements.
  function candidateText(element) {
    const parts = [];
    function visit(node) {
      if (node.nodeType === Node.TEXT_NODE) { parts.push(node.nodeValue); return; }
      const boundary = /^(DIV|P|BR|ARTICLE|LI|H[1-6])$/.test(node.nodeName);
      if (boundary) parts.push(' ');
      for (const child of node.childNodes) visit(child);
      if (boundary) parts.push(' ');
    }
    visit(element);
    return parts.join('');
  }
  function scan() {
    queued = false;
    const candidates = [...document.querySelectorAll(selector)].filter(post => !post.parentElement?.closest(selector));
    let matched = 0, hidden = 0;
    candidates.forEach(post => {
      const text = candidateText(post);
      const match = matches(text);
      if (match) matched++;
      const hide = enabled && revealed.get(post) !== text && match;
      if (hide) hidden++;
      post.classList.toggle('nopartisan-filtered', hide);
      let notice = post.previousElementSibling;
      if (notice?.dataset.nopartisanNotice !== 'true') notice = null;
      if (hide && showPlaceholders && !notice) {
        notice = document.createElement('div'); notice.dataset.nopartisanNotice = 'true';
        notice.className = 'nopartisan-notice';
        const button = document.createElement('button'); button.textContent = 'NOpartisan · Show filtered post';
        button.addEventListener('click', () => { revealed.set(post, candidateText(post)); post.classList.remove('nopartisan-filtered'); notice.remove(); queue(); });
        notice.append(button); post.before(notice);
      } else if ((!hide || !showPlaceholders) && notice) notice.remove();
    });
    document.querySelectorAll('[data-nopartisan-notice="true"]').forEach(notice => {
      if (!notice.nextElementSibling?.matches(selector)) notice.remove();
    });
    Object.assign(diagnostics, { candidates: candidates.length, matched, hidden });
    const summary = JSON.stringify(diagnostics);
    if (summary !== previousSummary) {
      console.info('[NOpartisan] scan', { ...diagnostics });
      previousSummary = summary;
    }
  }
  function queue() { if (!queued) { queued = true; setTimeout(() => { try { scan(); } catch (error) { queued = false; reportError(error); } }, 100); } }
  async function reload() {
    const { settings = NOpartisan.defaults, remoteList } = await browser.storage.local.get(['settings', 'remoteList']);
    enabled = settings.enabled;
    showPlaceholders = settings.showPlaceholders !== false;
    const keywords = [...new Set([...(remoteList || bundled).keywords, ...settings.custom].map(NOpartisan.normalize))];
    matches = NOpartisan.matcher(keywords);
    Object.assign(diagnostics, { enabled, keywordCount: keywords.length });
    queue();
  }
  const observer = new MutationObserver(records => {
    if (records.some(r => r.type === 'characterData' || [...r.addedNodes, ...r.removedNodes].some(n => n.nodeType === 3 || (n.nodeType === 1 && !n.closest?.('[data-nopartisan-notice]'))))) queue();
  });
  observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  browser.storage.onChanged.addListener((changes, area) => { if (area === 'local' && (changes.settings || changes.remoteList)) reload().catch(reportError); });
  await reload();
  diagnostics.initialized = true;
})().catch(reportError);
