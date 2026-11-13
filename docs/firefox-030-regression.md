# Firefox 0.3.0 investigation — 2026-11-13

Status: the reported Mark Levin example is a keyword coverage gap. A general
bundled-list regression has not been reproduced or ruled out on authenticated X.
This branch adds setup/permission guidance and regression checks; it does not
claim to close the live-site incident. No filtering rules or keyword data changed.

## Evidence

The development computer runs CachyOS Linux, Firefox 160.0 and Git 2.56.1.
No NOpartisan checkout was present. After network access became available,
cloned and fetched the repository, then created
`fix/firefox-030-filter-regression`. Installed checksum-verified official Node
24.22.3 under the user's local directory and ran `npm ci`.

The existing user's installed extension is active, signed AMO 0.3.0, with ID
`nopartisan@ohlongshawnson.github.io`, downloaded from
`https://addons.mozilla.org/firefox/downloads/file/5228976/nopartisan-0.3.0.xpi`.
The installed XPI SHA-256 is
`d6e27874e0ac10740e08e96ea48b90c17e3cb5dd3a9672577cc3cbba6a7d1ea9`.
Read-only inspection of persisted grants included all three filtering sites
and optional GitHub access. That existing profile was not automated or changed.

Compared 13 relevant AMO runtime files against original main: 12 byte-identical;
manifest JSON identical apart from its final newline. The bundled list is
version `2026-11-05.537802fbba04`, 869 keywords. It includes `Mike Lee`, not
`Mark Levin`. The scripts, CSS, inspection tool and web-accessible declaration
for keywords.json are present. The old missing-resource declaration bug is not
present in this package. Comparing 0.2.1 commit `41a375f` with 0.3.0 shows no
changes to content.js, x-adapter.js, content.css or keywords.json. Manifest changes
between those commits are version/description; host access patterns are unchanged.
Changes to the default update URL and options UI did not make downloads mandatory.

The user reports that adding Mark Levin to personal keywords makes it filter,
and removing that phrase leaves the Mark Levin item visible in X's What's
happening area. This agrees with the shipped list: the matcher has no Mark Levin
entry by default. There was no Mike Lee item available there to test. This is
not evidence that bundled initialization failed. No new keyword coverage is
being introduced during this investigation.

## Actual Firefox integration

`tests/firefox_integration.py` runs Selenium/geckodriver in disposable profiles.
It does not open the user's profile. It first installs the original signed
Mozilla XPI permanently in a clean profile, before installing any modified copy.
Firefox 160.0 confirmed:

- Empty extension storage, all 869 bundled entries load, no GitHub permission.
- The actual packaged matcher accepts Mike Lee and rejects Mark Levin.
- Runtime permissions.getAll includes all three declared filtering origins.
- The installed signed extension and bundled list remain available after restart.

The unauthenticated live X profile page exposed zero tweet articles. No live
post hiding was observed in that profile. Do not count visiting it as live
filtering validation.

A separate temporary development copy uses a distinct test ID, adds localhost
only to test match/host/resource patterns, and routes localhost paths to the
existing adapters. Production matching, initialization, storage, observer,
Reveal and CSS code remain unchanged. Firefox checks passed:

- Default bundled phrase filtering verified with computed display:none.
- Neutral content and absent Mark Levin phrase remain visible.
- Real options-form save adds Mark Levin and updates the already-open feed.
- Reveal restores a post's computed visibility.
- A dynamically inserted matching post filters.
- Disabling restores all posts; re-enabling filters matches again.
- Revoking host access prevents injection after refresh.
- Revoked X permission is reported in the development options UI.
- Simulating a host grant through Firefox's internal permission service and
  refreshing restores injection. This is a test-profile grant, not an observed
  user acceptance of the Firefox permission prompt.
- Basic existing Reddit and Facebook adapters filter matching local fixtures
  and preserve neutral items. These are fixture smoke tests, not live sites.

To rerun (Python virtual environment with selenium and a geckodriver binary):

```sh
GECKODRIVER=/absolute/path/to/geckodriver \
AMO_XPI=/absolute/path/to/nopartisan-0.3.0-amo.xpi \
python tests/firefox_integration.py
```

The runner enables Firefox remote system access only in its disposable test
process to locate extension pages and simulate a permission grant. It leaves
normal Firefox profiles and settings untouched.

## Changes and draft release notes

- First install opens setup; updates preserve the existing startup behavior.
- Setup explicitly explains the included offline keyword list and coverage gaps.
- Per-site access status and individual grant buttons request only the existing
  declared site selected by the user. Denial remains visible. Users are told to
  refresh existing tabs after granting access. GitHub access remains separate.
- Popup status directs users to check site access and active list if posts remain.
- Added permission UI, onboarding and manifest-origin consistency tests plus
  reproducible Firefox integration checks. Existing lifecycle/matching/migration
  tests remain in place.

Baseline: 35 Node tests passed; lint had zero errors/warnings/notices; build and
check:release passed. Final validation: 39 Node tests passed; lint reported zero errors, warnings and
notices; build and check:release passed. All 17 Firefox integration assertions
passed (signed-package checks plus local fixture checks). Version remains 0.3.0: this is a diagnostic/setup draft,
not a verified 0.3.1 filtering hotfix. Nothing was merged, published, or changed
on the OMV server.

## Required live acceptance before closing

Use a clean profile with signed 0.3.0 first, ensure the site grant and enabled
state, and search X for `"Mike Lee"` or another exact bundled phrase. Searching
is needed when the current trends contain no bundled phrase. Remove the test
phrase from personal keywords so the test actually exercises the bundled list.
If testing the bundle specifically, use fresh storage with no downloaded list.

Observe a matching actual post, scroll to newly loaded matching posts, disable
and re-enable, and restart Firefox. Check Reveal separately. Right-click a
visible matching post and choose **NOpartisan: Why is this post visible?**;
collect the report's state section (initialized, list source/version/count,
recognition, match and Reveal state). Feed excerpts can be redacted. If messaging
fails, collect local startup/scan/error diagnostics from the content-script
console. Routine logs contain counts rather than feed text.

Repeat granted/denied host access in the clean profile, and smoke-test actual
Reddit/Facebook feeds. These authenticated live tests and the full live restart
acceptance remain outstanding. Bump to 0.3.1 only after a filtering fix, if needed,
is identified and verified. A missing phrase alone should not trigger an engine
rewrite or an automatic download/privacy change.
