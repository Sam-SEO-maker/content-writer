---
name: source-research
description: >-
  Documents a topic or a URL with verified sources to feed the E-E-A-T brief
  before generation. Cascading research: curated per-subject library first, then
  web complement (deep-research / WebSearch / WebFetch) that enriches the
  library. Real, verified sources, never invented. Invocable on its own or
  called by the refresh orchestrator. Library read + write.
disable-model-invocation: false
---

# Source research: the E-E-A-T brief

Builds a foundation of **verified sources** for a topic/URL, upstream of
generation. Goal: feed E-E-A-T with real references (academic, institutional,
recent figures), **never fabricated**. This file carries the **method**
(cross-cutting, all sites); the details live in `references/` (read as needed):

- `references/source-quality.md`, quality grid per source type + ✅/❌ examples.
- `references/brief-schema.md`, full JSON schema of the brief + example + injection flow.
- `references/blacklisted-domains.md`, canonical list of the ~750 forbidden domains
  (competitors, aggregators, all Wikipedia editions) + subdomain rule,
  exceptions (Golden Rule, review article whose subject IS the platform) and substitutes.

The **directory** of authority domains (data, per site) lives on the site side, e.g.
`sites/superprof.fr-ressources/sources/authority-map.md`: the skill consumes it at
tier 1, it does not replace it.

> **Status: work in progress.** The foundation is built "top-down" (a subject
> directory → authorities per site, see tier 1) then enriched article by article
> (tier 3, the agent proposes → a human validates). Without a directory for a given
> site, the skill operates in "web only" mode (tiers 2-3) and bootstraps the
> directory along the way.

## Step 0: load the blacklist (mandatory, BEFORE any research)

**Read `references/blacklisted-domains.md` in full before any WebSearch,
WebFetch or deep-research call.** Keep the list in working memory for the whole
session and apply it **a priori**:

- A blacklisted domain is **never fetched** nor kept as a candidate; it is
  discarded as soon as the SERP or search results are read, not after the fact.
- Never package a "top N" of results without first sifting it against the
  blacklist: the filtering happens **before** curation, not after.
- In **batch / multi-article** mode: re-check the blacklist at the start of **each
  article** (re-read the file or re-summarise its categories); the constraint must
  never drop out of working memory between two iterations.

The two exceptions (Golden Rule on existing content, review article whose subject IS
the platform) are defined in `references/blacklisted-domains.md` and prevail.

## Cascading research (3 tiers)

### Tier 1: directory of authority domains (priority)
Draw first from `sites/<site-slug>/sources/`: the **directory** validated by a
human, reusable from one article to the next. For `superprof.fr-ressources`,
`authority-map.md` gives the authority domains **per subject**. Approach:

1. Identify the article's **subject** (history, maths, social sciences…).
2. Read the corresponding line of the directory → priority authority domains,
   source types to target, pitfalls to avoid.
3. Target these domains at tier 2.

> ⚠️ The directory says **where** to look (domains), never **which exact page**: do
> not invent a page URL. If the site does not yet have a `sources/` folder,
> go straight to tier 2 without inventing a path or content.

### Tier 2: targeted web research (effective resolution)
Query the domains selected at tier 1 (or, absent a directory, the field's primary
sources). Choose the tool based on the need:
- **`deep-research`** (skill) for a broad topic requiring multi-source
  verification and a cited report.
- **`WebSearch` / `WebFetch`** for spot checks (a stat, a date, a specific
  primary source).

Query best practices:
- **Blacklist first** (step 0 already done): a SERP/WebSearch result belonging
  to a blacklisted domain is **ignored without being fetched**; immediately look
  for a non-blacklisted alternative.
- **Restrict to the directory's authority domain** (`site:insee.fr`,
  `site:hal.science`) rather than an open search.
- **Target the precise page** (deep-link) that carries the information, never the homepage.
- **Trace back from an aggregator to the primary source**: from a press article or
  Wikipedia, go to the cited study / official text, and keep **that one**.
- **Discard upfront** any unresolved or undated source: it does not go into the brief.
  Detailed criteria: `references/source-quality.md`.

### Tier 3: directory enrichment
An **authority domain** newly confirmed at tier 2 is **proposed** for addition to
the site's directory (`sites/<site-slug>/sources/authority-map.md`), human validation
before integration. This is what grows tier 1 across articles. Add a
domain (where to look), not a page URL (which stays specific to one article).

## Source quality criteria

- **Primary preferred**: INSERM, INSEE, ministries, peer-reviewed
  journals, official bodies, rather than blogs/aggregators.
- **Never Wikipedia**: it is an aggregator, not a source. Trace back to the primary
  source it cites and keep that one in the brief.
- **Recent** when the data is dated (stats, regulations).
- **Verifiable**: resolvable URL, identifiable author/organisation.
- **Relevant** to the blog's E-E-A-T level (see the site's skill).

Detailed grid per source type (academic, institutional, press, figures)
+ ✅/❌ examples: `references/source-quality.md`.

## Output: the source brief

Return a structured list `sujet` / `sources[]` (`source`, `url`, `year`,
`claim`) / `lacunes[]`, each source tied to the **claim** it supports (so that
generation does not cite a source out of its scope). **Full schema, filled
example and injection flow**: `references/brief-schema.md`.

> The brief travels **as an argument** to the generation subagent (`content-generator`),
> it feeds the content and the `eeat_sources` field; it does not go through
> `generation_prompt.txt`. Details in `references/brief-schema.md`.

## Forbidden

- ❌ **Inventing a source or a figure.** An anecdote/statistic without a verifiable
  source is not written (cf. E-E-A-T Experience Proofs: do not fabricate
  numbered anecdotes).
- ❌ **Keeping Wikipedia as a source** in the brief: [[feedback-no-wikipedia-links]].
- ❌ **Citing/linking a blacklisted domain** (competitors, aggregators): the exclusion
  happens **a priori** (step 0: blacklist loaded before any research, candidates
  discarded before fetch). Filtering the final brief against
  `references/blacklisted-domains.md` remains a **safety net**, not the
  main mechanism; without an alternative, drop the claim (→ `lacunes[]`)
  rather than cite a forbidden domain.
- ❌ "Consulté le [date]" ("Accessed on [date]") in the returned references: [[feedback-no-consulte-le]].
- ❌ Em dash `—`: [[feedback-no-em-dash]].

## How it fits together

- **Invocable on its own**: "document this topic for me" → returns the source brief.
- **Called by the** `refresh` **orchestrator before** generation (the
  "Source research" step of the workflow), upstream of the writing skills
  ([[generate-enseigna-avis]], [[sp-ressources-gutenberg]]) that consume the brief.

## Dependencies to build (backlog, do not block on this)

1. Extend the `sites/<site-slug>/sources/authority-map.md` directory to the other
   sites (exists for `superprof.fr-ressources`).
2. Semi-automatic build script (agent proposes → human validates).
3. Deterministic wiring of the brief to the generator: today it travels as an
   argument to the subagent (see `references/brief-schema.md`); wiring like the PAA's
   (`MinimalRow` → `audit_data` → dedicated section of `generation_prompt.txt`) is still
   to be done to make it reproducible without intervention.
