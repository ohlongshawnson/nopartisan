# Privacy

NOpartisan processes feed text inside the current page. It sends no posts, keywords matched against posts, browsing history, or analytics to any server. It does not use an account, telemetry, external scripts, or synchronized storage.

Settings, custom keywords, downloaded keyword lists, and update timestamps/errors are stored in Firefox's local extension storage. Feed text and reveal state are not stored on disk. A user-requested post inspection passes extracted text through internal extension messages and browser session memory into a local extension page. The session copy is removed when the report opens; unopened reports disappear when the browser restarts or the extension unloads. Close the report tab to discard its displayed text. Reports are rendered as plain text and are never uploaded or added to routine console logs. Uninstalling removes extension storage through Firefox.

Optional updates contact raw.githubusercontent.com only after the user supplies a source and grants permission. GitHub and network providers can see the connection, including the user's IP address and requested list URL. Requests omit credentials and referrers. No feed content is included. By default there are no remote keyword requests.

The extension requires access to supported social sites to inspect and hide feed posts. Access is limited to www.reddit.com, x.com, and www.facebook.com. Browser and social-site network activity are separate from NOpartisan.
