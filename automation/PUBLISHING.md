# Automatic collection and publication

The OMV server publishes complete schema-1 keyword lists directly to
`ohlongshawnson/nopartisan` main. Routine updates do not create a PR. The collector
implementation and documentation are maintained on `feature/expanded-coverage`
for workstation review; runtime data and credentials are never pushed. The
separate manual proposal CLI remains available in [README.md](README.md).

## Inclusion and retention policy

Sources establish current political office or a specific political identity;
news headlines do not. The same rules apply to every affiliation, with no equal
party-count requirement. Coverage now includes Congress, the president and vice
president, Cabinet/selected Cabinet-level positions, governors, reviewed parties
and committees, two clearly political congressional organizations, and a small
reviewed set of election/campaign/legislative phrases. This is useful initial
coverage of those categories, not a claim to cover all political organizations.

Publication is additive: the complete current collection is deduplicated against
all previously published keywords. Former officeholders are not newly collected
from current directories, but previous political keywords remain useful for
historical coverage and are not automatically removed. A source failure aborts
the entire run and cannot erase a previously published category. There is no
fallback to cached/imported bodies. No keyword count target or party quota exists.

Official names come from current directory fields. Common full-name variants
come from House `namelist`, structured `first_name`/`last_name` and explicit
`nickname` fields. These are labeled source-field variants, not a claim that
all spellings are equally common. Cabinet aliases are individually reviewed,
found literally on the official page, and conditional on the named person still
appearing in a current role heading. No surnames alone, invented nicknames,
initial-only first-name variants, or automatic transliterations are added.

Explicit ambiguity exclusions live in `publishing.json`, with reasons. Examples:
John Carter (film/character), John Curtis (school), Al Green (singer), Bill Lee
(baseball), Mark Green (ordinary instruction), and short Green Party (decorations).
The exact `Gov. Bill Lee` profile heading is accepted instead of the bare name.
Al Green is currently withheld entirely because these sources do not provide a
sufficiently distinct name; House roster validation still includes his seat.
The Senate's misplaced-suffix composite `Angus S., Jr. King` is rejected in favor
of the actual structured `Angus S. King, Jr.` name. Complete names can still
match namesakes or nonpolitical coverage; this pipeline does not infer meaning.

## Sources and independent completeness checks

All sources below must succeed in each production run. Bounds apply separately,
not as one Senate-sized count applied to every category. Official pages are used
where available. NGA is the governors' association, **not a .gov directory**;
its current roster and matching profiles are the documented governor authority.

| Source | Completeness and extraction checks |
| --- | --- |
| [Senate XML](https://www.senate.gov/general/contact_information/senators_cfm.xml) | 90–100 unique IDs; all 50 states; at most two per state; exact membership/state/affiliation agreement with CSV |
| [House Clerk XML](https://clerk.house.gov/xml/lists/MemberData.xml) | Exactly the 441 expected districts from current apportionment, including delegates; 420–441 occupied; explicit vacancies; current Congress; publication date at most 60 days old; sworn date not in future; exact occupied-ID agreement with CSV |
| [Congress Legislators CSV](https://raw.githubusercontent.com/unitedstates/congress-legislators/gh-pages/legislators-current.csv) | Community-maintained corroboration; separate Senate 90–100 and House 420–441 bounds; unique bioguide IDs, state/affiliation/name agreement and official member URL domains. Optional empty full_name is allowed only with complete given/surname fields and official name evidence |
| [White House administration](https://www.whitehouse.gov/administration/) | Exactly President and Vice President role headings in main content; excludes spouses, navigation and biographies of other people |
| [White House Cabinet](https://www.whitehouse.gov/administration/cabinet/) | 15–35 unique name/office heading pairs; all 15 executive department roles, accepting current Defense/War label, plus explicitly listed Cabinet-level roles; ignores names mentioned only inside biographies |
| [NGA governors](https://www.nga.org/governors/) | Exactly 50 states plus five territories; each of 55 profiles must match roster name/state, identify affiliation, and have a started term marked Current. Missing optional state-government website links are recorded; those links are not claimed fetched |
| [FEC national committees](https://www.fec.gov/campaign-finance-data/campaign-finance-statistics/formula-calculations-statistical-tables-election-cycles-after-2010/) | All individually reviewed literal party/committee names must appear; only DCCC, DSCC, NRCC and NRSC are allowed as short organizational acronyms |
| [Democrats](https://democrats.org/), [Libertarian Party](https://lp.org/), [DSCC](https://www.dscc.org/), [NRCC](https://www.nrcc.org/) | Each page must retain every configured reviewed literal political identity; legal self-identification footers are valid evidence |
| [Congressional Progressive Caucus](https://progressives.house.gov/), [Republican Study Committee](https://rsc-pfluger.house.gov/) | Exact reviewed full organization names on their official sites; no general extraction from their news posts |
| [Senate glossary](https://www.senate.gov/about/research-tools/glossary.htm), [USAGov election process](https://www.usa.gov/presidential-election-process), [FEC campaign finance](https://www.fec.gov/introduction-campaign-finance/), [FEC PAC registration](https://www.fec.gov/help-candidates-and-committees/registering-pac/) | Small version-controlled, individually reviewed literal phrase sets; every phrase must still occur. No bulk glossary ingestion of ordinary words |
| [NPR Politics](https://feeds.npr.org/1014/rss.xml), [Fox Politics](https://moxie.foxnews.com/google-publisher/politics.xml) | Valid nonempty RSS/Atom, 1–500 items each; links and bounded titles validated. Known names get linked occurrence context; at most 40 unverified discovery spans are quarantined in discovery.json |

There are 19 top-level sources and 55 separately validated NGA profile requests.
Fresh HTTPS requests use the existing 15-second socket timeout, checked 30-second
read budget, 2 MB response limit, and one-second minimum request spacing.
Redirects, compression, XML DTD/entities, malformed sources and access failures
are rejected. No login, paywall, CAPTCHA or restriction is bypassed. No automatic
write retries or paid/AI API dependency is introduced. Articles are not fetched;
raw local feeds may contain feed text but are not committed or published.

## Review, validation and atomic publishing

Each collection generates `sources.json` with fetch times, SHA-256 hashes and
source-specific checks; `collected.json` with categories, identifiers, variants,
provenance and concerns; `collection-audit.json` with rejections/duplicates; and
`discovery.json` with explicitly unpublishable news leads. The extension still
receives **only** schemaVersion, version and keywords.

Before publication, `categorized-diff.json` and `.md` show additions by category,
merged duplicates, rejected candidates, and all retained legacy phrases without
literal current-run evidence. The latter flags review work, not a claim that all
such phrases are stale: for example the existing Donald Trump common spelling
is retained while the official heading spells Donald J. Trump. Joe Biden and
Kamala Harris remain legacy political keywords, not newly asserted officeholders.
Generic legacy MAGA/campaign/vote phrases also remain from the original list.
No previously published coverage is silently removed.

For a deliberate expansion, inspect the diff, run matching/false-positive checks,
then supply `--reviewed-sha256` from the dry run. A fresh production collection
must produce exactly that inspected complete-list digest or publication aborts.
Routine scheduled runs continue automatically under the reviewed extraction and
exclusion policy; they do not need an approval or PR for each unchanged/new roster.

NFKC, English/default Unicode lowercase (not casefold), ECMAScript whitespace
folding and literal word/phrase boundaries follow `extension/core.js`. All
phrases and normalized forms must pass schema 1, 1–10,000 phrases, 120 UTF-16
units per phrase, no control characters, and a 1,000,000-byte encoded limit. An
unchanged keyword set creates no commit and no version bump. Changed sets use a
UTC date plus a digest of the complete normalized set as the string version.

The GitHub writer reads main at one commit, verifies both existing JSON files
are byte-identical and valid, creates one tree based on that commit changing
only the two keyword files, and advances main with a single non-forced update.
Concurrent changes are rejected. Both committed files are read back before
success. No release tags or extension code are modified by the data publisher.
A timeout after ref advancement can leave an uncertain write outcome; the
intended commit is saved first and the next run reconciles remote truth.
`last-success.json` advances atomically only after verified success or a no-op.

## Deployment, credentials and operation

Runtime code is a root-owned installed snapshot at
`/opt/nopartisan-automation/automation`. Reinstall after tested source changes:

```sh
cd /root/projects/nopartisan
python3 -m unittest discover -s automation/tests -v
python3 -m automation.publish --data /root/nopartisan-data --dry-run
# Inspect the printed run directory's categorized-diff.md/.json and full output.
sh automation/install-systemd.sh
# For the reviewed expansion, from the installed runtime:
cd /opt/nopartisan-automation
python3 -B -m automation.publish --data /var/lib/nopartisan --reviewed-sha256 REPLACE_WITH_INSPECTED_OUTPUT_SHA256
```

Credentials remain in `/etc/nopartisan/github-token`, root-owned 0600 in a 0700
directory. Use a repository-scoped token with Contents read/write. The token is
never in Git, images, configuration JSON, command arguments, logs or state.
Scheduled runs use systemd LoadCredential and DynamicUser, with read-only system
and home protection, dropped capabilities and a ten-minute execution timeout.
Systemd-managed isolated 0440 credentials are accepted only under its declared
/run/credentials directory; ordinary token files must be 0600/0400.

State is outside the checkout at `/var/lib/nopartisan`, a systemd-managed link
to `/var/lib/private/nopartisan`. Run directories contain source snapshots,
previous and complete output JSON, categorized review, audit and result files.
Journald holds summaries and errors. A local file lock prevents overlapping runs.
The pre-expansion working tree was backed up outside Git under
`/root/nopartisan-data/backups/pre-expansion-20261105T175546Z.tar.gz`.

The existing timer remains daily at **04:30 America/Chicago plus a fixed delay
of up to ten minutes**, one-second accuracy, Persistent=true for missed runs.
No existing OMV or unrelated service is modified. Routine operations:

```sh
systemctl start nopartisan-publish.service
systemctl show nopartisan-publish.service -p Result -p ExecMainStatus
cat /var/lib/nopartisan/last-success.json
journalctl -u nopartisan-publish.service -n 60 --no-pager
systemctl list-timers nopartisan-publish.timer --no-pager
# Pause future runs; let any in-flight publisher finish:
systemctl disable --now nopartisan-publish.timer
# Resume:
systemctl enable --now nopartisan-publish.timer
```

Optional Docker build/dry-run remains non-root, read-only and credential-free:

```sh
cd /root/projects/nopartisan
export NOPARTISAN_DATA_DIR=/root/nopartisan-container-data
# Existing directory is owned by UID/GID 10001; do not recursively chown other data.
docker compose -f automation/compose.yaml build
docker compose -f automation/compose.yaml run --rm --entrypoint python pipeline -B -m automation.publish --data /data --dry-run
```

The Firefox source URL is unchanged:
`https://raw.githubusercontent.com/ohlongshawnson/nopartisan/main/keywords/politics.json`.
Firefox downloads the complete list when its configured automatic checks run
while the browser is open, or when a manual download is requested. The server
does not control the separate workstation or installed Firefox settings.

## Tests and review artifacts

Offline tests use saved factual fixtures and fake HTTP/GitHub transports. They
cover each new source's completeness, vacancies, current terms, identity/state/
affiliation conflicts, malformed inputs, aliases, ambiguity exclusions, separate
news discovery, categorized diffs, schema-1-only output, atomic writes, inspected
hash mismatch, source failures, remote conflicts and unchanged-list behavior.
No routine test uses live network or real credentials.

`automation/tests/check-matcher.cjs` runs unchanged `extension/core.js` against
`matcher-cases.json` and benchmarks both the previous and proposed complete list.
It tests political names and phrases, furniture/school/garden text, surname and
acronym ambiguity, and the documented movie/singer/baseball/school collisions.
The server budget is p95 below 25 ms/post for a 1,980-character benign sample,
1,600 iterations; compile time and a five-times-longer sample are also recorded.
This is a Node/V8 measurement, not a Firefox UI performance claim. Match timing
and representative false positives cannot guarantee all real browsing contexts.

The original Senate-only data publication was
[f99189a](https://github.com/ohlongshawnson/nopartisan/commit/f99189a9c1a96ee701a157fa9ca82b67dcfab94e).
Expansion run results and implementation commits are recorded below after the
reviewed live publication and production no-op check.


## Reviewed expansion published — 2026-11-05

The categorized dry run was inspected at
`/root/nopartisan-data/publishing/20261105T182317413270Z/`. Its `inspection.json`
records the session review, source checks, exclusions, output hash and benchmark.
The installed publisher recollected all sources and enforced the inspected hash
before advancing main.

Publication commit:
[`3379294f7d1210671bc51241c16d968ca8293221`](https://github.com/ohlongshawnson/nopartisan/commit/3379294f7d1210671bc51241c16d968ca8293221).
Production artifacts: `/var/lib/nopartisan/publishing/20261105T182828470878Z/`.
Complete list: **869 keywords**, **759 additions**, **zero removals**, 19,338 bytes;
schemaVersion **1**, version `2026-11-05.537802fbba04`.
SHA-256: `7395db7aaf447948ed137e00cb8717ae1dba0db6f57883c2378f257ac5c48254`.

| Category | Current phrases validated | Added phrases |
| --- | ---: | ---: |
| House | 613 | 613 |
| Senate | 136 | 36 |
| President / vice president | 2 | 2 |
| Cabinet / Cabinet-level | 23 | 23 |
| Governors | 55 | 55 |
| Parties | 5 | 4 |
| National committees | 12 | 12 |
| Congressional political organizations | 2 | 2 |
| Election phrases | 6 | 5 |
| Campaign phrases | 2 | 2 |
| Legislative phrases | 5 | 5 |
| Total current collection | 861 | 759 |
| Retained legacy phrases outside this run's literal evidence | 8 | 0 |

These are phrase counts, including supported name variants, not party quotas
or people counts. The source rosters validate all 439 seated House members and
two vacancies in 441 districts; accepted names cover 438 House members after
withholding Al Green for the singer collision. Other accepted identities are
100 senators, president and vice president, 21 Cabinet officials and 55 governors.

All 74 source checks passed. 671 duplicate phrase groups were merged. Eighteen
candidate records (ten distinct phrases) were rejected: the four namesake cases
Al Green, Bill Lee, John Carter and John Curtis; malformed Angus suffix order;
and the initial-only C. Franklin, H. Griffith, J. Correa, J. Hill and W. Steube.
Seventeen explicit policy exclusions also prevent generic words and ambiguous
acronyms, whether or not they appeared as proposed candidates in this collection.
Sixteen news-discovery leads remain quarantined and were not published.

The eight retained legacy phrases are Donald Trump, Joe Biden, Kamala Harris,
MAGA, political campaign, Republican Party, vote Democrat and vote Republican.
They are flagged separately; they do not assert that former officeholders hold
current office. No stale roster entries or future-sworn House members were newly
accepted. All governor profiles have a current, already-started term.

Validation passed: **45 offline Python tests**, including failure/no-op/hash-gate
and source-specific checks; **13 expansion tests in a non-root, network-disabled,
read-only container**; **19 political and 14 nonpolitical matcher cases** against
the unchanged extension code. The actual 869-keyword matcher compiled in 0.84 ms,
with a 0.74 ms median and **0.79 ms p95** per post (110-keyword baseline p95
0.12 ms). A 9,900-character benign sample took 2.96 ms. This is Node 24/V8 on
this server, not a Firefox UI measurement. Both live public JSON URLs were fetched
and verified byte-identical to the inspected output. Extension packaging passed.

Implementation and documentation are available on
[`feature/expanded-coverage`](https://github.com/ohlongshawnson/nopartisan/tree/feature/expanded-coverage),
with original history, MIT licensing and v0.1 unchanged. Runtime data, raw source
snapshots and the credential remain outside Git. The separate historical
[initial server record](SESSION.md) describes the earlier, restricted-access
session and is not the current deployment state.

The installed production service then completed a second fresh full collection at
`/var/lib/nopartisan/publishing/20261105T183105207014Z/`: **unchanged**, zero
additions, same version/hash and main commit. The existing timer was resumed and
is enabled/active; its next run is 2026-11-06 at 04:35:29 CST.
