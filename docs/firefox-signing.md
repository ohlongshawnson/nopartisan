# First unlisted Firefox signing submission

Candidate: **0.2.1**, desktop Firefox **142+**. Distribution: **unlisted / self-distributed**. This guide prepares signing; it does not submit or sign the ZIP.

## Permanent identity and development settings

`browser_specific_settings.gecko.id` is **`nopartisan@ohlongshawnson.github.io`**. This is an extension identifier, not an email account. Keep it unchanged for future versions. Mozilla checks ID availability/ownership during submission; no reservation is claimed here.

The previous temporary development ID was `nopartisan@example.org`. Its stored settings do not automatically migrate to the new ID. Before removing that development add-on, copy your personal phrases, source URL, and toggle choices from its settings into a local private note. Install the signed candidate, enter those choices in its full settings, grant optional GitHub access if needed, and download the list. Then disable the old temporary add-on so both do not filter the same feed. Do not commit your personal settings or Firefox profile to Git. Preparing this release does not edit or remove your existing Firefox profile data.

## Build and verify

With Python 3 and Node.js 24.15+:

```sh
npm ci
npm test
npm run lint
npm run build
npm run check:release
```

Unsigned upload package: `dist/nopartisan-0.2.1.zip`, with `manifest.json` at ZIP root. Checksum: `dist/nopartisan-0.2.1.zip.sha256`. From `dist`, run `sha256sum -c nopartisan-0.2.1.zip.sha256`.

The archive contains only reviewed runtime JS, HTML, CSS, keyword JSON, the supplied PNG logo, the manifest, and MIT LICENSE. There is no transpilation, bundling, minification, or generated executable code; all runtime source is readable in the ZIP. Node dependencies are development-only and are not shipped. No credentials, Git metadata, Firefox profile, reports, tests, or automation-server files belong in this upload.

## Account and submission — user action required

1. Sign in to the [Mozilla Add-ons Developer Hub](https://addons.mozilla.org/developers/), or create/link your Mozilla account. You must review and accept Mozilla's developer agreement yourself.
2. Start a new add-on submission and choose **On your own** (self-distribution/unlisted), rather than the public directory.
3. Upload `nopartisan-0.2.1.zip`; address any Mozilla validator findings. Select desktop Firefox compatibility; Android has not been tested.
4. The candidate contains original, untransformed runtime code. A separate transformed-source submission should not be needed. If Mozilla requests source, provide the matching release commit with these packaging instructions; do not upload credentials or unrelated server state.
5. Complete the unlisted submission using the release/reviewer notes below. After signing, download Mozilla's **signed XPI** from the version page. Do not modify it after signing.
6. In desktop Firefox, use `about:addons` → gear menu → **Install Add-on From File…** and choose that signed XPI. Transfer settings as described above and refresh existing supported tabs.

No Mozilla API credentials are needed for the web submission route. Keep any future signing API credentials outside the repository and uploaded artifacts.

## Notes for reviewers

NOpartisan hides feed items based on literal keyword phrases, irrespective of viewpoint. Host access is limited to Reddit, X, and Facebook. `storage` holds local preferences/list data; `alarms` handles optional keyword checks; `menus` supplies the user-initiated X diagnostic. No browsing-history, analytics, or post-content upload is implemented.

The optional GitHub permission is requested only when a user configures an HTTPS raw GitHub list. Downloads are schema-1 JSON data, bounded to 1 MB, validated, and escaped for literal matching; no remote code is executed. Failed updates retain the last valid list. The source and daily update toggle default to empty/off. GitHub receives ordinary network metadata on downloads, as documented in [PRIVACY.md](../PRIVACY.md). Post inspection uses internal extension messages and browser session memory; reports are consumed on opening and displayed as plain text.

Testing without a social account: load the extension, open its toolbar popup/full settings, and verify saved toggles. Authenticated feed testing needs a tester-owned social account; no private account credentials are supplied or required by the extension. Synthetic regression fixtures and tests are available in the repository. See [release notes](releases/0.2.1.md) for known limits.

Extension-binary auto-updates are not configured (`update_url` is absent). Initial unlisted builds are manually distributed. GitHub keyword downloads update data only, not the signed executable package.

## Mozilla references

- [Submission and self-distribution](https://extensionworkshop.com/documentation/publish/submitting-an-add-on/)
- [Extension IDs](https://extensionworkshop.com/documentation/develop/extensions-and-the-add-on-id/)
- [Source submission requirements](https://extensionworkshop.com/documentation/publish/source-code-submission/)
