# X content-script fix — 2026-11-05

## Root cause and evidence

The manifest correctly matched `https://x.com/*` and loaded `core.js` before `content.js`. The installed development Firefox profile granted access to X. Read-only inspection of NOpartisan's local Firefox IndexedDB record confirmed `settings.enabled: true` and `settings.custom: ["Mike Lee", "Republicans", "mike lee"]`, the exact key read by the content script. The settings save itself was working.

The script fetched `browser.runtime.getURL('keywords.json')` before reading storage or registering its mutation observer and storage listener. The resource was not declared in `web_accessible_resources`. In installed Firefox 159, the original initialization path reproduced this error on a local fixture:

```
TypeError: NetworkError when attempting to fetch resource.
Security Error: Content at http://127.0.0.1:8127/ may not load or link to moz-extension://…/keywords.json.
```

Thus the matching engine never received the saved keywords, and settings changes could not rescan the page. The original selector also scanned only tweet articles, excluding trends. Tests additionally exposed concatenated block labels (`PoliticsMike Lee1,000 posts`) defeating whole-word boundaries when reading raw `textContent`.

## Fix

- `extension/manifest.json`: declare only `keywords.json` accessible on the three existing supported origins; bump extension version to 0.1.1. No new host permissions.
- `extension/content.js`: include individual `[data-testid="trend"]` candidates alongside `article[data-testid="tweet"]`; preserve block text boundaries while reading posts, author names, and quoted content; use the same text extraction for Reveal. Exclude nested candidates to avoid duplicate placeholders. Never select the search field, entire sidebar, or timeline.
- `extension/content.js`: add local counts-only startup/scan diagnostics and explicit initialization/rescan error reporting. Matching and storage key names remain unchanged.
- `tests/x-content.test.cjs` and `tests/fixtures/x-feed.html`: regression coverage for the reported phrase and lifecycle; fixture markup is synthetic, not a captured authenticated X DOM.
- `package.json`, `package-lock.json`: align project version with the extension.
- `tools/package.py`: derive archive version from the manifest to avoid shipping a misleading archive filename.
- `README.md` and this record: reload instructions, diagnostics, and test evidence.

## Verification

`npm test`: 11 passing tests. Includes exact Mike Lee phrase, mixed case, duplicate entries, author text, quoted text and nested articles, individual trends, unrelated content remaining visible, settings rescans, keyword removal, new candidates, disabling, Reveal and recycled cards, initialization error reporting, and the bundled resource declaration.

`npm run lint`: zero errors, warnings, or notices.

`npm run build`: `dist/nopartisan-0.1.1.zip` (unsigned).

A separate Firefox 159 profile installed and ran the updated extension against the local HTML fixture. The isolated test copy added localhost to its match/permission/resource patterns, used a distinct test add-on ID, and mapped localhost to the X adapter. Production filtering and settings code were otherwise unchanged. Assertions checked computed CSS visibility, not just class names. Actual Firefox checks passed:

1. Exact phrase, mixed case, author and quote text, duplicate keywords, and individual trends filter.
2. Submitting the real options form updates an already-open tab.
3. Firefox storage contains the enabled flag and all three personal entries.
4. Reveal restores both a post and a trend.
5. Removing keywords restores content and removes placeholders.
6. Dynamically inserted posts and trends filter automatically.
7. Disabling filtering restores all hidden candidates.
8. No runtime or resource-access errors were recorded for that test extension.

The updated extension was explicitly installed in the test profile. The developer's existing authenticated Firefox could not be controlled because the browser access host was unavailable. X in the isolated profile redirected to sign-in, so no authenticated live DOM inspection was claimed.

The user then reloaded NOpartisan through `about:debugging`, refreshed the authenticated X search tab, and confirmed: **“Both posts and trend now hide.”** This confirms the reported live failure is resolved; it is user-observed evidence rather than agent-controlled live inspection.

Remaining authenticated-site checks: actual X scrolling/virtualization, current live quoted-post markup and author-only matches, and live use of keyword removal, disable, and Reveal. These behaviors passed synthetic DOM/Firefox fixture tests; they were not separately observed on authenticated X during this session.

No scraper, external server, service, or scheduled collector was changed. Diagnostics stay local and contain counts, not page content.
