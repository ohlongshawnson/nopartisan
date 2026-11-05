(async () => {
  const id = location.hash.slice(1);
  const key = `postInspection:${id}`;
  const stored = await browser.storage.session.get(key);
  if (!id || !stored[key]) throw new Error('This report is no longer available. Right-click the post and request a new inspection.');
  const report = stored[key];
  await browser.storage.session.remove(key);
  if (report.error) throw new Error(report.error);
  const summary = !report.initialized ? 'The content script did not initialize. See the initialization error below.' :
    !report.recognized ? 'The selected element is not inside an X post recognized by the adapter. Right-click the post text or image.' :
    report.activeListDiffersFromDownloaded ? 'The running tab uses a different list from the downloaded list in storage. Refresh the X tab and inspect again.' :
    !report.filteringEnabled ? 'Filtering is disabled.' :
    report.revealed ? 'This post was revealed for its current identity and content.' :
    !report.matched ? 'No active keyword matches the extracted text. This can be a coverage gap; text inside image pixels is not extracted.' :
    report.currentlyHidden ? 'This post matches and is hidden.' : 'This post matches but is currently visible; a scan may still be pending. If it remains visible, report the adapter/lifecycle issue.';
  document.getElementById('summary').textContent = summary;
  const { extracted, ...state } = report;
  document.getElementById('state').textContent = JSON.stringify(state, null, 2);
  for (const [id, value] of Object.entries({ outer: extracted?.outerText, author: extracted?.authorText, quote: extracted?.quotedText,
    alt: extracted?.imageAltText, accessible: extracted?.accessibleImageText })) {
    document.getElementById(id).textContent = (Array.isArray(value) ? value.join('\n\n') : value) || '(none available)';
  }
})().catch(error => { document.getElementById('summary').textContent = error.message; });
