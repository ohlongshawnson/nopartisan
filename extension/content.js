// Routine diagnostics contain counts only. Per-post reports require the context-menu action.
const diagnostics = globalThis.NOpartisanDiagnostics = {
  build: 'post-inspection-1', initialized: false, enabled: null,
  keywordCount: 0, candidates: 0, matched: 0, hidden: 0, runtimeErrors: 0
};
function reportError(error) {
  diagnostics.runtimeErrors++;
  console.error('[NOpartisan] content script error', error);
}
console.info('[NOpartisan] content script started', diagnostics.build);
(() => {
  const { X } = NOpartisan;
  const isX = location.hostname === 'x.com';
  const selectors = { 'www.reddit.com': 'shreddit-post, div[data-testid="post-container"]', 'x.com': X.candidateSelector, 'www.facebook.com': '[role="feed"] [role="article"]' };
  const selector = selectors[location.hostname];
  if (!selector) return;
  let bundled, enabled = true, showPlaceholders = true, matches = () => false, queued = false;
  let activeKeywords = [], list = null, previousSummary, initializationError = null;
  const revealed = new WeakMap(), notices = new Map(), managed = new Set();
  const extract = post => isX ? X.extract(post) : { segments: [X.text(post)] };
  const signature = (post, extracted) => JSON.stringify([isX ? X.identity(post) : null, extracted.segments]);
  function removeNotice(post) { notices.get(post)?.remove(); notices.delete(post); }
  function scan() {
    queued = false;
    const candidates = new Set([...document.querySelectorAll(selector)].filter(post => !post.parentElement?.closest(selector)));
    for (const post of managed) {
      if (!candidates.has(post)) { post.classList.remove('nopartisan-filtered'); removeNotice(post); revealed.delete(post); managed.delete(post); }
    }
    let matched = 0, hidden = 0;
    for (const post of candidates) {
      managed.add(post);
      const extracted = extract(post);
      const match = extracted.segments.some(matches);
      if (match) matched++;
      const hide = enabled && revealed.get(post) !== signature(post, extracted) && match;
      if (hide) hidden++;
      post.classList.toggle('nopartisan-filtered', hide);
      if (hide && showPlaceholders) {
        let notice = notices.get(post);
        if (!notice) {
          notice = document.createElement('div'); notice.dataset.nopartisanNotice = 'true';
          notice.className = 'nopartisan-notice';
          const button = document.createElement('button'); button.textContent = 'NOpartisan · Show filtered post';
          button.addEventListener('click', () => { revealed.set(post, signature(post, extract(post))); post.classList.remove('nopartisan-filtered'); removeNotice(post); queue(); });
          notice.append(button); notices.set(post, notice);
        }
        if (post.previousElementSibling !== notice) post.before(notice);
      } else removeNotice(post);
    }
    Object.assign(diagnostics, { candidates: candidates.size, matched, hidden });
    const summary = JSON.stringify(diagnostics);
    if (summary !== previousSummary) { console.info('[NOpartisan] scan', { ...diagnostics }); previousSummary = summary; }
  }
  function queue() {
    if (!queued) {
      queued = true;
      setTimeout(() => { try { scan(); } catch (error) { queued = false; reportError(error); } }, 100);
    }
  }
  async function reload() {
    const stored = await browser.storage.local.get(['settings', 'remoteList', 'lastUpdate', 'updateError']);
    const settings = { ...NOpartisan.defaults, ...stored.settings };
    const base = stored.remoteList ? NOpartisan.validate(stored.remoteList) : bundled;
    enabled = settings.enabled;
    showPlaceholders = settings.showPlaceholders !== false;
    activeKeywords = [...new Set([...base.keywords, ...settings.custom].map(NOpartisan.normalize).filter(Boolean))];
    matches = NOpartisan.matcher(activeKeywords);
    list = { source: stored.remoteList ? 'downloaded' : 'bundled', version: base.version, keywordCount: base.keywords.length,
      personalKeywordCount: new Set(settings.custom.map(NOpartisan.normalize).filter(Boolean)).size, activeKeywordCount: activeKeywords.length,
      configuredSource: settings.source, lastDownload: stored.lastUpdate || null, updateError: stored.updateError || null };
    Object.assign(diagnostics, { enabled, keywordCount: activeKeywords.length });
    queue();
  }
  function inspect(element) {
    const post = isX ? X.findPost(element) : null;
    const extracted = post ? X.extract(post) : null;
    const matchedKeywords = extracted ? activeKeywords.filter(keyword => extracted.segments.some(NOpartisan.matcher([keyword]))) : [];
    return { list, initialized: diagnostics.initialized, initializationError, filteringEnabled: enabled,
      recognized: Boolean(post), postIdentity: post ? X.identity(post) : null, extracted,
      matched: matchedKeywords.length > 0, matchedKeywords,
      revealed: Boolean(post && revealed.get(post) === signature(post, extracted)),
      currentlyHidden: Boolean(post?.classList.contains('nopartisan-filtered')) };
  }
  const observer = new MutationObserver(records => {
    if (records.some(record => !record.target.parentElement?.closest('[data-nopartisan-notice]') &&
      (record.type !== 'childList' || [...record.addedNodes, ...record.removedNodes].some(node => node.nodeType === Node.TEXT_NODE ||
        (node.nodeType === Node.ELEMENT_NODE && !node.matches('[data-nopartisan-notice]')))))) queue();
  });
  // Include changes that X makes while reusing a card or loading an accessible description.
  observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true,
    attributeFilter: ['role', 'alt', 'aria-label', 'aria-labelledby', 'aria-describedby', 'aria-hidden', 'hidden', 'href', 'data-testid', 'data-tweet-id', 'data-item-id', 'id'] });
  browser.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && (changes.settings || changes.remoteList) && bundled) reload().catch(reportError);
  });
  const ready = (async () => {
    bundled = NOpartisan.validate(await (await fetch(browser.runtime.getURL('keywords.json'))).json());
    await reload(); diagnostics.initialized = true;
  })().catch(error => { initializationError = error.message; reportError(error); });
  browser.runtime.onMessage.addListener((message, sender) => {
    if (sender.id !== browser.runtime.id || message.type !== 'inspectPost') return;
    return (async () => {
      await ready;
      // Observe the matcher actually in use; do not refresh it and hide a stale-tab defect.
      const stored = await browser.storage.local.get('remoteList');
      const downloaded = stored.remoteList ? NOpartisan.validate(stored.remoteList) : null;
      const downloadedListInStorage = downloaded ? { version: downloaded.version, keywordCount: downloaded.keywords.length } : null;
      const activeListDiffersFromDownloaded = list ? (downloaded ? list.source !== 'downloaded' || list.version !== downloaded.version || list.keywordCount !== downloaded.keywords.length : list.source === 'downloaded') : null;
      const element = browser.menus.getTargetElement(message.targetElementId);
      return { ...inspect(element), downloadedListInStorage, activeListDiffersFromDownloaded };
    })();
  });
})();
