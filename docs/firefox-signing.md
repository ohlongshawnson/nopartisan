# Firefox 0.3.1 release preparation

Local candidate: **0.3.1**, desktop Firefox **142+**, permanent ID
`nopartisan@ohlongshawnson.github.io`. Submit as a new version of the existing
[NOpartisan Mozilla listing](https://addons.mozilla.org/en-US/firefox/addon/nopartisan/),
not a new extension identity. No submission or signing is performed by these steps.

```sh
npm ci
npm test
npm run lint
npm run build
npm run check:release
```

Unsigned candidate: `dist/nopartisan-0.3.1.zip`; checksum:
`dist/nopartisan-0.3.1.zip.sha256`. The archive has manifest.json at its root and
contains reviewed readable runtime assets plus LICENSE, without development
packages, tests, credentials, Git metadata or automation files.

Before submission, update the listing description and privacy disclosure using
[listing copy](mozilla-listing.md) and [PRIVACY.md](../PRIVACY.md). This release
moves HTTPS raw.githubusercontent.com access from optional to installation-time
host permissions. Disclose the initial and daily GitHub downloads, ordinary IP
and requested-file metadata, the opt-out, and the offline fallback. Keep the
manifest's no-data-collection declaration consistent with the implementation:
no user payload, identifiers or telemetry are uploaded.

Use [reviewer notes](mozilla-reviewer-notes.txt) and [release notes](releases/0.3.1.md).
Review the candidate and its checks before authorizing upload to the existing
version page. If an agreement is required, the account owner must accept it.
Download the signed XPI unchanged and validate its manifest, ID, version,
permissions, included resources and behavior in a clean normal Firefox profile.
Installing the local ZIP temporarily does not test Mozilla's actual install
prompt, signing or production upgrade delivery.

Existing users retain their saved preferences, custom sources, cached lists and
explicit opt-outs. Fresh installs update automatically after installation grants;
users can revoke any host grant. Downloads contain schema-1 data only, never
executable code. No OMV services, schedules or deployments are changed.

References checked on 2026-11-13:

- [Firefox MV3 host permissions and installation grants](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/host_permissions)
- [Firefox permission origin normalization](https://github.com/mozilla-firefox/firefox/blob/main/toolkit/components/extensions/ExtensionPermissions.sys.mjs)
- [Current Mozilla add-on policies](https://extensionworkshop.com/documentation/publish/add-on-policies/)
- [Built-in data-consent taxonomy](https://extensionworkshop.com/documentation/develop/firefox-builtin-data-consent/)

Mozilla has announced revised policies for December 1, 2026; recheck if submitting
after that date. Signing and authenticated live-site acceptance remain separate
from the local automated checks.
