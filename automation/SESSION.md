# Initial server session — 2026-11-05

Environment observed: host `mementos`, Debian 13.7 (trixie), kernel
6.12.113+deb13-amd64, OMV 8.6.0-1, Python 3.13.5, Git 2.47.3,
Docker CE 29.9.2 and Compose 5.6.1. Node.js is absent.

`/root` is a writable persistent bind of `/dev/nvme0n1p2` (ext4), with about
511 GB free. Project: `/root/projects/nopartisan`; generated data:
`/root/nopartisan-data`. `/srv` contains OMV disk UUID mountpoints and mergerfs
storage, but is read-only to this session. No storage remounts were attempted.
No applicable AGENTS.md was found in the project or ancestor directories.

The session is restricted: Docker daemon access is denied, shell networking
(including DNS) fails, systemd bus access is denied, and only session processes
are visible. Enabled unit symlinks identify existing Docker/containerd, OMV engine,
nginx, PHP FPM, SMB/NFS, cron/anacron, SSH, Mosquitto, monitoring and storage
services. Their running state and container inventory could not be verified.
No OMV-managed configuration or existing service was modified. No packages,
scheduled jobs, or host services were installed. No credentials were requested.

`git clone` failed on shell DNS. The connected GitHub reader recovered all Git
blobs, trees, three commits and the annotated tag. Each reconstructed object's
SHA-1 was checked against GitHub, and `git fsck --full` passed. Original main is
`e83259447fc00fa6621569c85101ded265012837`, and the original `v0.1` tag object is
`a27b1a588a9364223e041d75ca603727efbff093`. All history, tests and MIT licensing
are intact. Feature branch: `feature/manual-keyword-pipeline`. No remote write.

Live data was acquired using the connected GitHub reader from the pinned Congress
Legislators CSV documented in README.md, then imported through the CLI with its
actual fetch timestamp and transport. The upstream gh-pages commit is dated
2026-09-24; it is not a current official directory. This distinction and staleness
are flagged on every proposal. Official member links are verification leads,
not claimed fetched evidence. The browser reader refused Senate XML as unsupported
text/xml, returned 403 for the Senate HTML index, and refused NPR XML as unsupported.
No access restrictions were bypassed. A direct CLI collection failed DNS for all
four configured sources, emitted a report and returned exit code 2.

Latest successful imported-source run at implementation completion:
`/root/nopartisan-data/runs/20261105T171725404384Z/`.
It has 12 pending full-name candidates (5 Democrat, 5 Republican, 2 Independent),
88 Senate names deferred by batch size, and 439 House records outside scope.
There were zero published duplicates/excluded Senate names, zero source duplicates,
and zero feed entries. Three optional sources have explicit missing-import errors.
The starter ten keywords and their version are unchanged in both published files.

Candidates: Adam B. Schiff; Angus S. King, Jr.; Alan Armstrong; Alex Padilla;
Bernard Sanders; Ashley Moody; Amy Klobuchar; Bernie Moreno; Andy Kim; Bill Cassidy;
Angela D. Alsobrooks; Bill Hagerty. Evidence is in the local report, not an invented
headline. Official verification and namesake/nonpolitical-context review remain
necessary. Initials, suffixes and formal names may reduce matching recall.

Validation: 17 offline Python tests passed; Compose configuration validated;
extension packaging succeeded; `git diff --check` and `git fsck --full` passed.
The tests exercise patch application and synchronization only inside temporary
fixture repositories. Existing JavaScript tests/lint could not run without Node
and its dependencies. Docker image build/runtime could not run without daemon
access. A future session with permitted network/daemon access should verify direct
official/feed collection and the container runtime before adopting either.

The human review step remains outstanding. No real candidate approval, published
list patch, scheduled collection, automatic publication or GitHub PR was performed.
