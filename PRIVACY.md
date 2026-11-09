# Privacy

NOpartisan processes feed text inside the current page. It sends no posts, keywords matched against posts, browsing history, or analytics to any server. It does not use an account, telemetry, external scripts, or synchronized storage.

Settings, custom keywords, downloaded keyword lists, and update timestamps/errors are stored in Firefox's local extension storage. Feed text and reveal state are not stored on disk. A user-requested post inspection passes extracted text through internal extension messages and browser session memory into a local extension page. The session copy is removed when the report opens; unopened reports disappear when the browser restarts or the extension unloads. Close the report tab to discard its displayed text. Reports are rendered as plain text and are never uploaded or added to routine console logs. Uninstalling removes extension storage through Firefox.

Every installation includes the complete bundled schema-1 list and filters offline immediately. The maintained default update source is `https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json`. No network permission or download is needed for filtering. A user action to enable daily updates or choose **Update filters now** requests optional access to `raw.githubusercontent.com`; declining leaves local filtering available. Updates run daily only while Firefox is running when enabled.

GitHub and network providers can see ordinary connection information, including the user's IP address and requested list URL. Requests omit credentials and referrers. Feed content, browsing history, personal keywords, and matched phrases are never sent. Failed, empty, or invalid downloads preserve the last valid list.

The extension requires access to supported social sites to inspect and hide feed posts. Access is limited to www.reddit.com, x.com, and www.facebook.com. Browser and social-site network activity are separate from NOpartisan.
