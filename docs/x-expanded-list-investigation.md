# X missed-post investigation — 2026-11-05

## Preserved state and evidence

The desktop checkout was clean at the start. Fetch found published commit `3379294f7d1210671bc51241c16d968ca8293221` on `main` and the server implementation on `feature/expanded-coverage`. Desktop main was fast-forwarded to the two published keyword updates only. No server implementation, source configuration, scheduler, publisher, or keyword coverage was edited. Both published schema-1 JSON files remain identical.

Read-only inspection of NOpartisan's existing Firefox profile storage showed:

- Filtering enabled.
- GitHub source set to the repository's main keyword file; automatic extension downloads enabled.
- Downloaded version `2026-11-05.537802fbba04`, 869 keywords.
- Last successful download `2026-11-05T18:51:21.317Z`, no stored update error.
- Four personal entries. The supplied text fragments matched none of them.

Thus an outdated download is not supported by the observed profile state. This was a stored-state snapshot, not direct access to the running content-script sandbox; the new per-post report identifies what each running tab actually uses. An old tab or unreloaded extension remains distinguishable from current storage.

No screenshot attachment was accessible to this session. Only the user's supplied fragments were examined. No authenticated live DOM or actual image alt attributes were available: the browser access host was unavailable, and the isolated Firefox test profile has no X sign-in. No complete-post diagnosis is inferred from an incomplete description.

## Example findings

| Example | Evidence and classification |
| --- | --- |
| Rich Neumeister; quote contains “Klobuchar/Walz”, “Senate”, “Tim” | Neither the published nor active personal list matches these supplied fragments. The published list contains `amy klobuchar` and `tim walz`, but not bare `klobuchar`, `walz`, `senate`, or `tim`. This is a demonstrated coverage gap for the supplied wording. The old recursive DOM reader already included ordinary quoted DOM text, so visibility alone does not prove a quote extraction defect. Synthetic quote tests and the new report verify extraction separately. Other text in the actual complete post remains unverified. |
| Dustin Grage; “Minneapolis elected Mayor Morality 2.0.” | No published or active personal keyword matches this author/sentence fragment. This is a coverage gap, not evidence of a literal matcher failure. The phrase's political meaning is not inferred by the existing matcher. |
| “FOUR WOMEN. FOUR HISTORIC FIRSTS.” inside an image | The supplied caption fragment itself has no keyword match, and pixel text was never extracted. Actual alt/ARIA descriptions are unknown until inspected on the live post. The old extractor omitted image descriptions even if useful ones existed; this client omission is fixed. A generic alt such as `Image` still supplies no political names. A rich alt containing a listed full name now filters. No OCR or semantic classification was added. |

No ambiguous surname or generic political term was added to either keyword file. If broader recall is desired, propose contextual rules separately—for example, a surname near a political role or multiple corroborating political references. Require ordinary-text negative examples to reduce namesake and everyday-word false positives. Contextual matching is a recommendation, not an implemented global keyword expansion. Image OCR is a separate future option; the present evidence does not establish its necessity.

## Client changes

- `x-adapter.js`: scoped tweet/trend boundaries; separate outer, author, quoted, image-alt, and other accessible image text. Unknown quote wrappers stay in the outer-text fallback. Description ID references are followed only within the same post. Words split across inline spans are preserved; full names separated by slashes retain whole-word matching.
- `content.js`: match each extraction segment; rescan alt/ARIA/role and status-link changes. Reveal signatures include post identity and extracted content so a recycled same-text card for a new status ID does not inherit Reveal. Notices follow their owning cards and are cleaned up on removal or adapter-boundary changes.
- User-requested native context menu: opens `inspection.html` with active list metadata, initialization/enabled state, target recognition, text sections, matches, identity, hidden state, and Reveal state. The report also compares the running matcher’s list metadata with the saved download without refreshing the matcher, so inspection does not conceal a stale-tab defect. Post text stays in internal extension messages and session memory, is consumed on opening, and is displayed only in the local extension page. No page-specific report or phrases are logged or uploaded. Reports use separate session keys so one cannot consume another.
- Manifest version 0.2.0 adds only the `menus` API permission and extraction dependency; no new site access. Popup provides a discovery hint. Package version, documentation, and privacy text are updated.
- Existing tests use a pinned starter-list fixture for personal-keyword add/remove behavior rather than depending on a server-updated list. New tests use the actual 869-keyword list and representative synthetic markup.

## Validation

- `npm test`: 21 passing tests, including all previous behavior plus schema/list reporting, screenshot-fragment coverage distinctions, explicit/unknown quotes, slash-separated full names, author-only matches, image alt and ARIA descriptions, outside-post ID-reference exclusion, dynamic descriptions and quoted content, recycled card identity, adapter boundary removal, old-list/new-list changes, unrecognized targets, internal message authorization, plain-text rendering, session consumption, and absence of post text in routine logs.
- `npm run lint`: zero errors, warnings, or notices.
- `npm run build`: unsigned `dist/nopartisan-0.2.0.zip`.
- Actual Firefox 159 tests used an isolated profile with the real 869-keyword list and `tests/fixtures/x-missed-posts.html`. A temporary test copy added localhost to the existing host/resource/menu patterns and mapped that hostname to the X adapter. No target-element lookup or extraction function was stubbed.
- A real WebDriver BiDi right-click on the fixture triggered Firefox's native context menu; invoking its actual menu item exercised `menus.getTargetElement`, background-to-content messaging, session report transport, and the extension report page. Clicking within the quoted text selected the correct outer post and reported the quote, 869 keywords, and no matches. Right-clicking the image reported its generic `Image` alt without claiming OCR.
- Firefox also verified filtering on quoted/slash-separated full names, author text, useful alt and ARIA descriptions, late-loaded/removed image alt, dynamically inserted quote text, recycled same-text status IDs resetting Reveal, and consumed session reports.

These are fixture tests, not authenticated live-X checks. The user was asked to reload the temporary extension, refresh X, and inspect the actual missed posts. Their live adapter recognition, quote grouping, image descriptions, and current tab initialization remain to be confirmed if no user result has been received. Post-specific report text should stay local; only recognition/count/availability findings need to be shared.
