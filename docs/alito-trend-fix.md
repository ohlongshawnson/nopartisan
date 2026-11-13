# Automatic political trends and vocabulary — 2026-11-13

## What failed and what changed

The 0.3.0 snapshot had 869 phrases but omitted politics, political, Samuel Alito
and Justice Samuel Alito. With the standard data-testid=trend markup, its
shipped defaults demonstrably leave the exact category/title card visible.
Baseline reproduction before code changes: empty custom list -> visible;
custom politics alone -> hidden; custom Justice Samuel Alito alone -> hidden.
The neighboring FursuitFriday card stays visible. This proves a default-coverage
defect, not a need for the user to maintain a basic political dictionary.

It does not prove the live screenshot's DOM shape or rule out a separate site
injection/recognition defect. Authenticated browser access remains unavailable.
No new alternative selector was guessed: the existing selector is retained;
trend extraction and inspection now explicitly recognize individual cards.

Changes:

- 38 permanent curated terms in keywords/foundational.json, mirrored in the
  extension. Complete schema-1 canonical and bundled feeds now have 903 terms.
- Content initialization loads both packaged lists. Foundation is always unioned
  with the chosen bundled/downloaded list and personal phrases. An older or
  names-only server update cannot remove the local foundation.
- Separate X.politicalCategory rule recognizes explicit Politics/Political labels
  inside each recognized trend. Topic title matching is not required. Category
  extraction is bounded to that card; News is not automatically political.
- Inspection now recognizes trends, with category/topic extraction, category rule
  result, build marker trend-foundation-1, extension version, keyword presence and
  DOM/extracted-text checks, hiding class and computed style. Routine logs remain
  counts only. The existing user-initiated context menu and local session report
  lifecycle are preserved.
- Release/package checks prevent omitting foundation from the complete feed or
  diverging its copies. Existing collector publishing is additive; consecutive
  name-update regression tests verify foundation is retained. No collector
  deployment, service, scheduling or production writes were performed.

False-positive considerations are in keywords/FOUNDATIONAL.md. No OCR or
contextual AND/OR rules were added. The canonical feed changes here are local;
they have not been published to main or to the server.

## Verification

- npm test: 45 passing tests, including new automatic-default trend cases and
  a release test rejecting removal of politics from both complete feed copies.
- Python automation tests: 47 passing; no remote writes.
- npm run lint: zero errors, warnings or notices.
- npm run build and npm run check:release: pass, schema 1, 903 synchronized terms.
- Firefox 160.0 integration: 24 passing assertions. First installs the unchanged
  signed AMO 0.3.0 XPI in an isolated profile, then tests a separate temporary
  development copy with a distinct ID and localhost routing/matches. No existing
  user Firefox profile is touched.

The development fixture profile blocks external HTTP/HTTPS via an unreachable
proxy, bypassing localhost only. With empty storage, no GitHub download and no
personal keywords, computed CSS confirms:

- Politics · Trending / Justice Samuel Alito hidden automatically.
- Gaming · Trending / Grand Theft Auto VI, News · Trending / Weather forecast,
  FursuitFriday, the sidebar container, and neutral content stay visible.
- A foundation-only senate/election post hides automatically.
- Inserted political trends hide; reclassifying a recycled trend as Gaming
  restores it. Reveal and disable/re-enable remain functional.
- A names-only remote update retains foundational filtering and category blocking.
- Actual native context-menu invocation on a revealed trend opens a report that
  identifies the updated build, trend type, category match and Reveal state.
- Denied host access prevents injection; a test-profile simulated grant plus
  refresh restores it. Reddit/Facebook existing adapters pass local smoke tests.

The runner is tests/firefox_integration.py; invocation is documented in its
previous investigation record. These are actual Firefox tests of synthetic DOM,
not an authenticated live X capture. The signed original still lacks the new
rules. Version stays 0.3.0 until live verification supports preparing 0.3.1.

## Exact remaining authenticated test

1. Create a separate Firefox profile with about:profiles, open it, then load
   extension/manifest.json from this hotfix checkout via
   about:debugging#/runtime/this-firefox -> Load Temporary Add-on. This tests the
   changed source, rather than the installed Mozilla 0.3.0. Do not replace your
   usual signed installation or enable two NOpartisan builds in one profile.
2. Grant X site access, leave filtering enabled and personal keywords empty.
   Do not download anything. Sign in to X manually and refresh Home.
3. For an individual Politics · Trending card (the Alito example if still
   available), confirm only that card becomes a placeholder. Gaming/technology/
   entertainment neighbors must remain. Disable filtering to locate its title,
   enable to hide it again, disable to restore, then enable again. Scroll for
   newly loaded political cards. Do these toggle checks before Reveal.
4. Click that card's Reveal placeholder, then right-click its visible category
   or title and choose NOpartisan: Why is this post visible?. Expected state:
   build trend-foundation-1; initialized true; filteringEnabled true;
   candidateType trend; recognized true; categoryMatched true; revealed true;
   list.personalKeywordCount 0; politics active in keywordChecks. The category
   and topic panels should include Politics · Trending and Justice Samuel Alito.
   ComputedHidden is expected false after Reveal. Reload to clear Reveal and
   confirm it hides automatically again.
5. A temporary add-on disappears on Firefox restart. Reload this development
   add-on after restart for further testing. End-to-end restart acceptance of
   the changed build requires a signed candidate or an appropriate dedicated
   developer test setup; the original signed installation's restart persistence
   was tested separately. Do not report changed-build live restart acceptance
   from the signed-original restart test.

If a matching card remains visible, inspect it directly without Reveal and share
its report state plus category/topic panels (redact feed excerpts as desired).
The report distinguishes unavailable content script, unrecognized candidate,
active versus absent phrase, DOM versus extracted-text differences, category
matching, disabled filtering, Reveal and computed CSS failure. An unrecognized
card requires the actual smallest card's outer HTML to resolve any live selector
change. Live X DOM, live scrolling, changed-build restart and live Reddit/Facebook
acceptance remain unverified. No merge, push or Mozilla publication occurred.
