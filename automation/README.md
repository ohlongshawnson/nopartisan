# Manual keyword proposals

For the now-active automatic publisher and server schedule, see
[PUBLISHING.md](PUBLISHING.md). This page documents the separate manual proposal
CLI; its approval gate does not apply to automatic updates under the publishing
policy explicitly authorized on 2026-11-05.

This MIT-licensed, Python 3.13 standard-library CLI collects public political directory
records and creates **unapproved** review artifacts. It runs once and exits. There is
no scheduler, web server, GitHub writer, AI service, or publication command.

Initial scope: US federal elected legislators, with a **Senate-only first batch**.
The same full-name/office evidence rule applies to every source affiliation. An
alphabetic round-robin sample across affiliations limits review workload; it does
not establish complete or equal viewpoint coverage. Organizations, slogans,
hashtags, House members, executive officials, former officials and non-US politics
are future work. A mention of politics does not qualify a business, celebrity,
journalist, or ordinary word for inclusion.

## Files and persistent data

Run commands from the repository root (`/root/projects/nopartisan` on this server).
No installation or Python dependencies are necessary.

- Code/configuration: `automation/`; source selection: `automation/sources.json`.
- Default persistent data: `~/nopartisan-data`, outside the checkout. Override
  with `--data /absolute/path` **before** the subcommand.
- Imported snapshots: `imports/<source-id>.body` and accompanying `.json` metadata.
- Each collection: `runs/<UTC timestamp>/`, containing source bodies,
  `candidates.json`, `report.md`, and `proposed-additions.json`.
- Approvals and patches: choose output paths under the external data directory.
  Existing files are never overwritten by approval/patch output.
- No credentials are needed. Keep any future credentials outside code/data/image,
  and do not copy workstation credentials. Generated data, caches, `.env` files,
  and secret directories are ignored. Do not force-add generated data to Git.

## Sources and boundaries

The configured structured dataset is the community-maintained
[Congress Legislators project](https://github.com/unitedstates/congress-legislators),
using its [CSV at immutable commit 577ca042](https://raw.githubusercontent.com/unitedstates/congress-legislators/577ca04282d14688cb14f6559eb27b52bdc50dfc/legislators-current.csv).
This is **not an official federal directory**. The pinned export was updated on
2026-09-24. Every record needs current official verification, and snapshots over
30 days old receive an extra warning. Discovery time is not a claim of current
office. Pinning aids reproducibility; it does not maintain freshness. To update
the pin, inspect the project's gh-pages branch, verify the new commit and export,
update both `url` and `snapshot_date`, then recollect and review. CSV exports lack
term dates, so they cannot independently verify current membership.

The preferred official source is the
[Senate contact directory XML](https://www.senate.gov/general/contact_information/senators_cfm.xml).
The two configurable discovery feeds are
[NPR Politics](https://feeds.npr.org/1014/rss.xml) and
[Fox News Politics](https://moxie.foxnews.com/google-publisher/politics.xml).
These are a small starter set, not a claim to represent every viewpoint. Feed
adapter tests cover RSS and Atom. Feed titles can only attach a mention to an
already directory-backed full name. Unmatched titles produce no new phrases.
Article pages are never fetched; reports store a link and brief occurrence
context, not headlines or article text. Raw local feed snapshots may include feed
text for reproducibility; they are ignored by Git and never published.

Sources are explicit trusted local configuration, limited to eight public HTTPS
URLs. Requests have no login/cookie handler, no API token and no redirect following.
They refuse compression, DTD/entities, unexpected structures, malformed records,
and responses above 2,000,000 bytes. Requests start at least one second apart,
have a 15-second socket timeout and a 30-second read budget checked between reads
(a blocking read can extend that budget by its socket timeout). There are no
automatic retries. Do not configure internal DNS aliases or private sources;
literal private IPs and localhost are rejected. This is an operator CLI, not a
service accepting untrusted URLs. Do not bypass access restrictions. Inspect
source terms/access failures before changing URLs.

Failures are written to stderr **and** the report. Optional-source failures permit
a clearly marked partial report. Required-source failures or zero candidates return
exit code 2; those reports cannot be approved. Parser/validation errors also return
2. A successful partial run returns 0 with `source_errors` greater than zero.
There is no silent fallback between direct requests and imported snapshots.

## Collect and review

```sh
cd /root/projects/nopartisan
python3 -m unittest discover -s automation/tests -v
python3 -m automation.pipeline --data /root/nopartisan-data collect --limit 12
```

The collection prints its exact run directory. Review `report.md`, then inspect
the machine-readable `candidates.json` for source hashes, fetch times, exclusions,
deferred names and brief office evidence. `proposed-additions.json` contains only
the proposed IDs/phrases and a report hash; it is deliberately not an extension
keyword list. No candidate is implicitly approved.

For an independently fetched source, import it explicitly:

```sh
python3 -m automation.pipeline --data /root/nopartisan-data import-source \
  --source legislators --file /root/nopartisan-data/imports/legislators-current.csv \
  --fetched-at 2026-11-05T17:11:42Z \
  --transport 'Connected GitHub reader; immutable commit 577ca04282d14688cb14f6559eb27b52bdc50dfc'
python3 -m automation.pipeline --data /root/nopartisan-data collect --imports-only --limit 12
```

Replace the timestamp/transport with the actual acquisition details for new
imports. Import verifies source structure and records a SHA-256 digest. The digest
protects local integrity; it is not a source signature. The session's connected
reader supplied UTF-8 text which was saved with LF line endings (180,609 bytes,
versus the upstream CSV's 181,149 bytes with CRLF). Its local digest is
`926c99cb6e1025153a56cf603a700b12aa92e1cd43f1d6789ccedf697e680ec9`.
Evidence records accurately identify that transport. Imported-only runs report
unavailable snapshots for unimported sources; they perform no network requests.

Normalization follows `extension/core.js`: NFKC, English/default Unicode
lowercase (not casefold), ECMAScript whitespace folding, then trimming. Source
phrases and normalized phrases are both checked. Control characters, invalid
UTF-16 lengths, invisible formatting, single names and non-name tokens are
rejected. Duplicate comparison uses normalized phrases against both lists and
the candidate pool. Directory-backed multiword names remain ambiguous: namesakes,
nonpolitical coverage, middle initials, punctuation and suffixes need review.
No nicknames or shortened variants are inferred. Literal names with initials or
suffixes have lower recall because punctuation is significant to the extension.
Python and Firefox can ship different Unicode database versions; common US names
are covered by fixtures, and unusual new characters need matcher verification.

For each phrase, verify the official member link, current role and affiliation,
preferred name, namesake risk, representative political/nonpolitical matches,
and whether the likely benefit justifies hiding unrelated mentions. Check the
same criteria across affiliations. The starter list remains illustrative:
`MAGA` can match acronyms/other languages, broad campaign/election phrases can
hide historical or neutral discussion, and people can appear in nonpolitical
stories. Whole-word matching prevents `MAGA` matching `magazine`; it does not
solve semantic ambiguity. Missing Congress, executive and minor-party coverage
is not remedied by automatically adding generic terms or surnames.

## Explicit human approval, then patch only

**Do not run the following until a human has reviewed the selected phrases.**
Use the run path printed by collection and its candidate IDs. Unselected IDs
remain unapproved; recollect/review corrected names instead of editing a report
after approval. Document the resolution of concerns in the approval reason.

```sh
RUN=/root/nopartisan-data/runs/REPLACE_WITH_REVIEWED_RUN
python3 -m automation.pipeline approve --run "$RUN" \
  --ids REPLACE_WITH_COMMA_SEPARATED_REVIEWED_IDS --reviewer 'Your name' \
  --reason 'Specific evidence checked and concerns resolved' \
  --acknowledge-concerns --out /root/nopartisan-data/approval.json
python3 -m automation.pipeline patch --run "$RUN" \
  --approval /root/nopartisan-data/approval.json --version '2026-11-05.1' \
  --out /root/nopartisan-data/approved-additions.patch
git apply --check /root/nopartisan-data/approved-additions.patch
```

Choose a distinct version for an actual keyword-set change. No-op approvals
produce an empty patch and preserve version/formatting. Approval binds the exact
report and published baseline hashes and includes reviewer, time and reason.
This is a local human workflow, not cryptographic authorization or enforced
separation of duties. Patch generation revalidates the set and size, refuses stale
baselines and mismatched bundles, and outputs identical changes to
`keywords/politics.json` and `extension/keywords.json`. It **does not apply** them.
Only after separately reviewing the diff should you apply it on a feature branch
and run packaging checks. No real approval or keyword patch was created this
session. These manual proposal/patch commands do not push, merge, move tags, or publish.

## Docker Compose

No daemon, service, port, privileged mode, or Docker socket mount is configured.
The container runs as UID/GID 10001 with a read-only filesystem, dropped
capabilities and bounded resources. Only its data directory is writable. Canonical
and bundled input lists are mounted read-only so baseline checks see local edits.
Code is built into the image; rebuild after changing it. The build context excludes
Git metadata, generated data and secrets. No dependencies are installed from PyPI.

On a host/session with Docker daemon access, prepare a **new**, separate data
directory for UID 10001 (do not recursively change existing shared storage):

```sh
install -d -o 10001 -g 10001 -m 0750 /root/nopartisan-container-data
export NOPARTISAN_DATA_DIR=/root/nopartisan-container-data
docker compose -f automation/compose.yaml config --quiet
docker compose -f automation/compose.yaml build
docker compose -f automation/compose.yaml run --rm pipeline collect --limit 12
```

The container CLI already supplies `--data /data`; use `/data/runs/...` and
`/data/approval.json` inside container commands. Approval and patch subcommands
otherwise take the same arguments. Write their outputs under `/data`. Container
patch generation still needs separate host review/application. Do not use
`compose up` as a persistent deployment. Pin a reviewed base-image digest before
relying on reproducible container builds; the starter image uses the Python 3.13
minor tag. Docker runtime/build verification was unavailable in this session.
Run the offline tests on the host with Python and Git; the runtime image does not
install Git, which is used only to check/apply fixture patches in tests.
