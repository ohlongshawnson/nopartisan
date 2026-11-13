(async () => {
  const id = location.hash.slice(1);
  const key = `postInspection:${id}`;
  const stored = await browser.storage.session.get(key);
  if (!id || !stored[key]) throw new Error('This report is no longer available. Right-click the post and request a new inspection.');
  const report = stored[key];
  await browser.storage.session.remove(key);
  if (report.error) throw new Error(report.error);
  const summary = !report.initialized ? 'The content script did not initialize. See the initialization error below.' :
    !report.recognized ? 'Candidate element not recognized. Right-click inside an individual post or trending-topic card.' :
    report.activeListDiffersFromDownloaded ? 'The running tab uses a different list from the downloaded list in storage. Refresh the X tab and inspect again.' :
    !report.filteringEnabled ? 'Filtering is disabled.' :
    report.revealed ? 'This item was revealed for its current identity and content.' :
    !report.matched && report.keywordChecks?.some(check => check.active && check.presentInDOMText && !check.extracted) ? 'An active keyword appears in DOM text but not extracted text. Check extraction below; hidden DOM text may also account for the difference.' :
    !report.matched && report.keywordChecks?.some(check => !check.active && check.extracted) ? 'An inspected phrase is extracted but absent from the active keyword list. See keywordChecks.' :
    !report.matched && report.keywordChecks?.some(check => check.active && !check.extracted) ? 'No match. An inspected keyword is active but absent from extracted text. Check category/topic extraction below; an unrelated item also produces this result.' :
    !report.matched ? 'No active keyword or political category matches. Inspect keywordChecks to distinguish an absent keyword from missing extracted text.' :
    report.currentlyHidden && report.computedHidden === false ? 'Match succeeded and hiding class is present, but computed CSS does not hide the item.' :
    report.currentlyHidden ? 'This item matches and is hidden.' : 'Match succeeded but the item remains visible; a scan may still be pending.';
  document.getElementById('summary').textContent = summary;
  const { extracted, ...state } = report;
  document.getElementById('state').textContent = JSON.stringify(state, null, 2);
  for (const [id, value] of Object.entries({ outer: extracted?.outerText, author: extracted?.authorText, quote: extracted?.quotedText,
    alt: extracted?.imageAltText, accessible: extracted?.accessibleImageText, category: extracted?.categoryText, topic: extracted?.topicText })) {
    document.getElementById(id).textContent = (Array.isArray(value) ? value.join('\n\n') : value) || '(none available)';
  }
})().catch(error => { document.getElementById('summary').textContent = error.message; });
