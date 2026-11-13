# Permanent political foundation

`foundational.json` is curated product data, separate from collected names. Its
38 entries cover political categories, parties, elections, institutions, roles
and political phrases. Changes require review; collection does not rewrite it.
`politics.json` remains a complete schema-1 feed including these terms, and
`extension/keywords.json` is its identical bundled snapshot.

The extension separately loads its packaged foundational.json and unions that
foundation with the selected bundled/downloaded list and personal phrases.
Thus even an old names-only download cannot remove the foundation. The existing
publisher merges additively, retaining the foundation already in the complete
feed; a regression test verifies consecutive name updates preserve it. Packaging
and release checks reject a complete feed missing a foundational entry. No
collector deployment, schedule, or service change is needed for these safeguards.

These are word/phrase matches, not a claim of semantic classification. `liberal`
and `conservative` can describe nonpolitical attitudes, arts or financial
choices; `democratic` can describe organizations; `senate` can name university
bodies; `governor` can describe a mechanical component; `ballot`, `voting` and
`elections` can occur in clubs. Including these requested core terms favors
political recall at that cost. Reveal and the disable control remain available.
Bare `party`, `left`, `right`, `news`, `candidate`, and `president` are omitted
because of especially broad ambiguity. News category labels alone do not trigger
the platform category rule.

The X category rule is separate from the matcher: an explicit Politics or
Political label within an individual recognized trend card qualifies regardless
of its title or the downloaded list. Other cards and the sidebar container do
not inherit that category. English category labels are currently supported.
