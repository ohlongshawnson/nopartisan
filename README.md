# NOpartisan

**No left. No right. No thanks.**

A privacy-focused Firefox extension that filters political feed posts regardless of party, ideology, or viewpoint. Early development: text filtering for Reddit, X, and Facebook. The bundled list is a snapshot of the server-published list; keyword coverage remains incomplete and false positives are possible.

## Try it in Firefox

1. Open `about:debugging#/runtime/this-firefox`.
2. Choose **Load Temporary Add-on** and select `extension/manifest.json`.
3. Click the NOpartisan toolbar action for quick filtering and placeholder toggles, or choose **Open full settings**.
4. Visit a supported feed and grant the requested site access. Reload existing tabs after installation.

Temporary add-ons disappear when Firefox restarts. Release distribution requires Mozilla signing; the generated ZIP is unsigned. The permanent extension ID is `nopartisan@ohlongshawnson.github.io`. See [unlisted signing and test installation](docs/firefox-signing.md) before replacing the old temporary development install.

Filtering matches whole words and phrases without case sensitivity, with Unicode normalization and whitespace folding. A placeholder lets you reveal each hidden post. Turning filtering off restores posts. User keywords supplement the active bundled or downloaded list. Text inside images and video is not analyzed. Site DOM changes may break adapters; authenticated live feeds have not yet been verified.

## Keyword updates

The extension works offline with `extension/keywords.json`. To enable GitHub downloads, enter:

`https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json`

Save settings to grant optional GitHub access, then download manually or enable daily checks. Checks run only while Firefox is running. This is an extension update check, not a collection service. The repository owner is deliberately not hard-coded. Only raw GitHub URLs inside a `nopartisan` repository are accepted. Redirects, oversized responses, and malformed lists fail without replacing the last successful list. Changing or clearing the source resets the downloaded list. Clearing the source also removes GitHub access.

Lists use schema version 1: `{ "schemaVersion": 1, "version": "2026-11-05", "keywords": ["political campaign"] }`. Lists must contain 1–10,000 nonempty phrases of at most 120 characters. Maximum response size is 1 MB. Keep `keywords/politics.json` and `extension/keywords.json` identical when shipping bundled updates.

Keyword data can still cause false positives. Review changes for context and viewpoint coverage. Avoid ambiguous everyday words. A compromised repository can affect what is hidden, but cannot provide executable extension code. GitHub HTTPS and repository review are the current trust boundary; cryptographic list signing is not implemented.

## Development

No build step is required to load the extension. With Node.js 24.15+ and Python 3:

```
npm ci
npm test
npm run lint
npm run build
npm run check:release
```

Build output: `dist/nopartisan-0.2.1.zip`. Development dependencies are never included in the extension. On the initial workstation, Node is locally installed under `~/.local/share/nopartisan-tools/current/bin`; add that directory to PATH for these commands.

Pure matching and validation live in `extension/core.js`; `content.js` handles site adapters and dynamic posts; `background.js` handles updates; `options.*` contains settings. Tests exercise matching, remote source validation, and feed lifecycle behavior.

## Separate automation server

Keyword collection and automatic publishing run separately on Environment B, the OMV server. The server implementation is maintained on `feature/expanded-coverage`; it publishes the complete schema-1 list to `main`. The workstation does not install or run the server scheduler. Desktop releases preserve the latest published list and keep both JSON copies synchronized.

Repository: [ohlongshawnson/nopartisan](https://github.com/ohlongshawnson/nopartisan). Licensed under the [MIT License](LICENSE).

## X filtering diagnostics

The v0.1 release includes the Firefox MV3 initialization fix and individual X trend filtering. After changing extension code, reload NOpartisan in `about:debugging#/runtime/this-firefox`, then refresh existing social tabs. Reloading a page alone does not reload the temporary extension.

In the page's Firefox Developer Tools Console, filter for `[NOpartisan]`. Build `post-inspection-1` logs startup and scan summaries: initialization, enabled state, unique active keyword count, candidate count, match count, hidden count, and runtime error count. Summaries log only when those values change. Logs contain no feed text or matched keywords and are never transmitted. `matched` can exceed `hidden` when filtering is disabled or a post is revealed. `NOpartisanDiagnostics` is also available in the extension's content-script context, not the page's default JavaScript context.

See [the X debugging record](docs/x-filter-debug.md) for the root cause, verification evidence, and remaining live checks.

In settings, uncheck **Show a placeholder for filtered content** and save to hide matching posts and trends without a placeholder or Reveal button. Existing installations keep placeholders enabled until changed. Saving updates already-open tabs.

The toolbar popup saves both quick toggles immediately, using the same global preferences as full settings. Changes apply to already-open supported tabs. Pausing filtering preserves your keywords and other settings. No new browser permissions are required.

The initial Git release is tagged `v0.1`; the extension and package use version `0.1.0`. Earlier 0.1.x numbers in the debugging record refer to development builds before this first commit.

## Clone onto the automation server

On the OMV server, choose an existing persistent project directory, then run:

```sh
git clone https://github.com/ohlongshawnson/nopartisan.git
cd nopartisan
git log -1 --oneline
git tag --list
```

Cloning does not install or start any services. Server-side automation should be developed in this repository, separately from the working extension. Push access will require separate authentication on that machine; do not copy workstation credentials into the repository or a Docker image.

## Inspect an X post locally

Reload the temporary extension in `about:debugging`, refresh X, then right-click inside a post and choose **NOpartisan: Why is this post visible?**. Version 0.2.0 adds the `menus` permission for this action, without adding website permissions.

The report opens in an extension page and shows the active list source, version, base and personal keyword counts, enabled state, running-versus-stored list differences, adapter recognition, extracted outer/author/quoted text, available image alt and accessible descriptions, matched phrases, and Reveal state. Right-clicking outside a tweet produces an explicit unrecognized-target result. Quote grouping is best-effort; unfamiliar quote markup is still scanned as outer post text.

Reports are generated only on request. Their text is passed through internal extension messages and temporary browser session memory, removed from that memory when opened, and rendered as plain text in the extension page. Nothing is sent to external services or written to routine logs or disk storage. Close the report tab to discard its displayed text. An unopened report remains in session memory until browser restart or extension unload. Refreshing an already-consumed report requires a new inspection.

X filtering includes existing image alt text and accessible image descriptions. It does **not** read pixels, perform OCR, or classify the political meaning of a post. Full names separated by `/` match existing whole-word rules; surname-only references do not match a full-name keyword. See [the expanded-list investigation](docs/x-expanded-list-investigation.md) for evidence and coverage gaps.

## First signed test release

Version **0.2.1** is prepared for Mozilla’s **unlisted / self-distributed** signing route. The generated ZIP is unsigned until Mozilla signs it. [Release notes](docs/releases/0.2.1.md) and [submission steps](docs/firefox-signing.md) document the package, identity, privacy, and test limitations. No extension-binary update server is configured; keyword downloads are a separate mechanism.
