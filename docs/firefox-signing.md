# First unlisted Firefox signing submission

Candidate: **0.3.0**, desktop Firefox **142+**. Distribution: **unlisted / self-distributed**. This guide prepares signing; it does not submit or sign the ZIP.

## Permanent identity and development settings

`browser_specific_settings.gecko.id` is **`nopartisan@ohlongshawnson.github.io`**. This is an extension identifier, not an email account. Keep it unchanged for future versions. Mozilla checks ID availability/ownership during submission; no reservation is claimed here.

The permanent ID is unchanged from the 0.2.1 candidate. Firefox settings saved under that ID remain attached to it. The older temporary development ID `nopartisan@example.org` has separate storage; if you still use it, copy your personal phrases, custom source, and toggle choices into a local private note before removing it, then restore them in the signed extension. Do not commit personal settings or your Firefox profile to Git.

## Build and verify

With Python 3 and Node.js 24.15+:

```sh
npm ci
npm test
npm run lint
npm run build
npm run check:release
```

Unsigned upload package: `dist/nopartisan-0.3.0.zip`, with `manifest.json` at ZIP root. Checksum: `dist/nopartisan-0.3.0.zip.sha256`. From `dist`, run `sha256sum -c nopartisan-0.3.0.zip.sha256`.

The archive contains only reviewed runtime JS, HTML, CSS, keyword JSON, the supplied PNG logo, the manifest, and MIT LICENSE. There is no transpilation, bundling, minification, or generated executable code; all runtime source is readable in the ZIP. Node dependencies are development-only and are not shipped. No credentials, Git metadata, Firefox profile, reports, tests, or automation-server files belong in this upload.

## Account and submission — user action required

1. Sign in to the [Mozilla Add-ons Developer Hub](https://addons.mozilla.org/developers/), or create/link your Mozilla account. Review and accept Mozilla's developer agreement yourself.
2. Start an add-on submission and choose **On your own** for self-distribution, not the public AMO listing.
3. Upload `nopartisan-0.3.0.zip`, address any validator findings, and select desktop Firefox compatibility. Android is not tested.
4. If asked whether source code needs uploading, the shipped runtime files are already readable and have no bundling, transpilation, minification, or generated executable code. Select no separate transformed-source package. If Mozilla requests supporting build details, use this guide and the matching public GitHub commit; no server credentials or private data are needed.
5. Enter the reviewer notes below, continue, and wait for Mozilla to sign. Download the signed XPI from the version page. Do not modify it after signing.
6. Install the signed XPI in desktop Firefox using `about:addons` → gear menu → **Install Add-on From File…**. Refresh supported feed tabs.

No Mozilla API credentials are needed for the web submission route. Keep any future signing API credentials outside the repository and uploaded artifacts.

## Notes for reviewers

NOpartisan hides feed items based on literal keyword phrases, irrespective of viewpoint. It includes the complete schema-1 political list in `keywords.json` and filters offline immediately. Host access is limited to Reddit, X, and Facebook. `storage` holds local preferences/list data; `alarms` handles optional keyword checks; `menus` supplies the user-initiated X diagnostic. No browsing-history, analytics, or post-content upload is implemented. Plain-text copy is in [mozilla-reviewer-notes.txt](mozilla-reviewer-notes.txt), ready to paste into Mozilla's reviewer-notes field.

The default maintained source is `https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json`. Optional GitHub access is requested only after a user chooses **Update filters now** or enables daily updates. Downloads are schema-1 JSON data, bounded to 1 MB, validated, and escaped for literal matching; no remote code is executed. Failed updates retain the last valid list. GitHub receives ordinary network metadata, including the user's IP address and requested URL. Feed content and personal keywords are never sent. Post inspection uses internal extension messages and browser session memory; reports are consumed on opening and displayed as plain text.

Testing without a social account: load the extension, verify its bundled filters, and open settings to test toggles and optional updates. Authenticated feed testing needs a tester-owned social account; no private account credentials are supplied or required by the extension. Synthetic regression fixtures and tests are available in the repository. See [release notes](releases/0.3.0.md) for limitations and validation detail.

Extension-binary auto-updates are not configured (`update_url` is absent). Initial unlisted builds are manually distributed. GitHub keyword downloads update data only, not the signed executable package.

## Mozilla references

- [Submission and self-distribution](https://extensionworkshop.com/documentation/publish/submitting-an-add-on/)
- [Extension IDs](https://extensionworkshop.com/documentation/develop/extensions-and-the-add-on-id/)
- [Source submission requirements](https://extensionworkshop.com/documentation/publish/source-code-submission/)
