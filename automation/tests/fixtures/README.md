# Fixture provenance

`legislators.csv` contains six actual Senate records selected (first two per
affiliation in file order) from the Congress Legislators CSV at commit
`577ca04282d14688cb14f6559eb27b52bdc50dfc`, retrieved on 2026-11-05 through the
connected GitHub reader. Full source URL and local snapshot hash are documented
in `automation/README.md`. These are saved test data, not current-office claims.

`senate.xml` is a **synthetic format fixture** made from the first selected CSV
record. It was not downloaded from the official Senate XML endpoint.

`news.xml` and `atom.xml` are **synthetic news**, with clearly labeled fixture
titles and example.org links. They must never be cited as actual news evidence.
`malformed.xml` is an intentionally hostile DTD/entity fixture.

Routine tests use these local files and fake HTTP responses only, without network.

`publishing-senate.xml` is six **actual official directory records**, selected by
the same bioguide IDs as legislators.csv, from a direct HTTPS fetch of
`https://www.senate.gov/general/contact_information/senators_cfm.xml` on 2026-11-05
at approximately 17:39 UTC. Its complete source snapshot and hash are retained
outside Git in `/root/nopartisan-data/publishing/20261105T173953406625Z/`.
It includes the official suffix-placement case for Angus King. The publisher
tests use an in-memory GitHub transport and an explicit fake token; they never
contact or publish to GitHub.

`publishing-v1.json` preserves the original Senate-only publishing configuration
for regression tests. Production uses policy version 2 in automation/publishing.json.

`expanded/` contains format-simplified factual fixtures retrieved on 2026-11-05:
all House districts and Congress identity/name fields; White House role/name
headings; the NGA roster and current-term/profile facts; and literal reviewed
political identity/terminology strings. Full source URLs are in its provenance.json.
House committee assignments, governor biographies, copyrighted articles, contact
details not needed by the parser, credentials and runtime reports are excluded.
Evidence-page HTML is explicitly synthetic markup containing verified phrases,
not a representation of the complete original page. Cabinet biography aliases
are saved as factual name strings only. Test dates are frozen to the fixture date
so routine tests require neither network nor a refreshed real-world roster.

`matcher-cases.json` contains synthetic sentences for political matches and
nonpolitical false positives. These are tests, not real news evidence.
