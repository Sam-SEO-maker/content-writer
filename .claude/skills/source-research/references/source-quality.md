# Source quality: grid by type

Reference loaded on demand from `source-research`. How to judge whether a source
deserves to enter the E-E-A-T brief. **Key principle**: always prefer the
**primary** source (the one that produces the information) over an aggregator that relays it.

## 1. Academic (journals, theses, laboratories)

The highest level of trust when the source is properly identified.

- ✅ Peer-reviewed journal article, resolvable DOI, authors + institution
  (e.g. on hal.science, cairn.info, a university journal).
- ✅ Thesis or signed laboratory report (CNRS, INSERM, INRIA), dated.
- ❌ "A study showed that…" with no journal name, no author, no year.
- ❌ Predatory article / non-indexed journal presented as "scientific".

Reliability signals: peer review, DOI, affiliation, verifiable bibliography.

## 2. Institutional (official bodies, ministries)

The backbone of E-E-A-T for educational and YMYL topics.

- ✅ Page from a whitelisted organisation (`education.gouv.fr`, `insee.fr`,
  `legifrance.gouv.fr`, `unesco.org`…) carrying the precise information.
- ✅ Official PDF report with issuing organisation and date on the cover.
- ❌ Commercial reuse of an official figure (merchant site) instead of the organisation.
- ❌ Homepage or category page of the organisation, without the precise data point.

Reference whitelist: `edito-refresh/references/eeat-framework.md`. Per-subject
directory (FR Ressources site): `sites/superprof.fr-ressources/sources/authority-map.md`.

## 3. Reference press

Useful for news, context, expert quotes. Treat it as a relay, not
as the primary source of a figure.

- ✅ Dated, bylined article from a recognised outlet (Le Monde, Libération, Le Figaro, BBC…),
  used for a fact or an attributed quote.
- ✅ Use it as a springboard: trace back to the study/report cited in the article and link
  **that one** for the figure.
- ❌ Opinion piece presented as established fact.
- ❌ Wire-copy rehash with no primary source when a figure is at stake.

## 4. Figures (statistics, reports)

A statistic only enters the brief with **source + year**, otherwise search engines
treat it as stale.

- ✅ `[figure] + [organisation] + [year]` (e.g. "Selon l'INSEE (2025), …").
- ✅ Results/table page from the organisation, year of the data explicit.
- ❌ Figure without a year, or the page's publication year confused with the year of
  the data.
- ❌ Figure "in circulation" with no identifiable producer.

## Traps (immediate rejection)

- ❌ **Wikipedia as a source**: an aggregator, never an E-E-A-T authority. Trace back to
  the primary source it cites and keep that one: [[feedback-no-wikipedia-links]].
- ❌ **Undated source** when the data is datable (stat, regulation, news).
- ❌ **PDF/page with no identifiable author or organisation**.
- ❌ **Disguised marketing content**: product page, agency blog, commercial
  comparison site presented as neutral.
- ❌ **Forums, social networks, uncredited personal blogs** (except the official account
  of an institution, used as such).
- ❌ **Homepage / category page** instead of the precise page carrying the information
  (cf. mandatory deep-link, `sites/superprof.fr-ressources/prompts/site.md`).

## Output

Never write "Consulté le [date]" ("Accessed on [date]") in the returned references:
[[feedback-no-consulte-le]]. Each retained source is tied to the **claim** it
supports (schema: `brief-schema.md`).
