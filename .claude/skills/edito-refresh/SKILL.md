---
name: edito-refresh
description: >-
  Cross-cutting SEO/GEO/E-E-A-T editorial rules to make articles rank (all
  sites). Actionable guidelines applied to every refresh: direct answer at the
  start of each H2, sourced statistics and quotes, semantic density by
  occurrences (not in %), institutional sources, GEO-ready structure,
  freshness. The details (9 GEO strategies, E-E-A-T ❌/✅ pairs, SOSEO/DSEO)
  live in references/, loaded on demand. Complements format-wordpress (form)
  and the site's skill (site-specific structure/tone).
disable-model-invocation: false
---

# Editorial rules: SEO / GEO / E-E-A-T (cross-cutting)

**Substance** rules common to all sites, applied to every refresh to
maximise ranking (SERP + generative engines). This file carries the actionable
part; details and examples live in `references/` (read as needed):

- `references/geo-strategies.md`, the 9 GEO 2026 strategies in detail + examples.
- `references/eeat-framework.md`, the 4 E-E-A-T pillars with ❌/✅ pairs and signals.
- `references/semantic-density.md`, the SOSEO/DSEO model (density by occurrences).

> The **per-site numeric values** (min/max length, number of external links)
> live in `config/site.json` (`seo_settings`). This guide sets the cross-cutting
> rules; it does not redefine those numbers.

## 1. Direct answer (AI extraction)

Generative engines extract **the first sentences** of each section.
Every `<h2>` is followed by a **direct answer in 1-2 sentences** (40-60 words),
before any elaboration. Same for every FAQ question (50-100 word answer).

## 2. Proof: sourced statistics and quotes

- **≥ 2 recent** numeric statistics (2025-2026), in the format `[figure] + [source] + [date]`.
  French content example ✅: « Selon le DEPP (2026), 40% des collégiens bénéficient d'un soutien scolaire. »
- **≥ 1 expert quote** with verifiable credentials (name, title, institution).
- Never a statistic without a date (treated as outdated by LLMs).

## 3. Institutional sources

- **≥ 3 institutional sources** cited with a link (uniform, all sites).
- The **authority domains** are **per-site** knowledge, not cross-cutting:
  the site's directory `sites/<site-slug>/sources/authority-map.md` (per subject + a
  cross-cutting base), consumed via the `source-research` skill. The *types* of
  domains to target (governmental, academic, statistical): `references/eeat-framework.md`.
- **Never link to Wikipedia** (all sites): cite the primary source that
  Wikipedia aggregates (study, official text, institution), never the encyclopedia article.
  Wikipedia is not an E-E-A-T authority source and weakens the signal.
- **No "Sources" block / author bio in the HTML**: the author and their credentials
  are handled by WordPress (profile), outside the article body. (Site format
  exception: Superprof Ressources has its own Gutenberg Sources block, see its skill.)

## 4. Semantic density: by occurrences, NOT as a percentage

Never reason in "density %". Aim for **coverage** (breadth of the semantic
field) without **over-optimising** (repetition). Caps:

- Main keyword (exact): **3-6 occurrences** (H1 + intro + 1-2 H2s + conclusion).
- Top topic terms: 2-5 occurrences each, distributed.
- Any term with ≥ 3 occurrences → vary with a synonym/paraphrase in ≥ 50% of cases.
- SOSEO/DSEO target: **variable per each query's SERP**, never uniform.
  Compute the **average scores of the TOP 3** and of the **TOP 10** (YTG guide:
  `top3_soseo`/`top3_dseo`, `top10_soseo`/`top10_dseo`); the article must have a
  **SOSEO above** those averages and a **DSEO strictly below** those
  averages. Details + examples: `references/semantic-density.md`.

## 5. AI-extractable formats

- Bullet lists for enumerations, comparison tables for summaries.
- Explicit Q&A format in the FAQ (**3-5 PAA questions** by default; extended FAQ possible
  if the article type warrants it).
- Short sentences (15-20 words), subject-verb-object structure, jargon defined.

## 6. Freshness

- Updated statistics and dates (2025-2026 sources), outdated years corrected
  in titles and body.
- **Never** change the date without a substantial modification (penalised by Google).
- Do not modify existing URLs or academic citations.

## 7. GEO-ready structure (reminder)

Direct answer after the H2 → sourced elaboration → expert quote → list of points.
Paragraph template and full article structure: `references/geo-strategies.md`.
The **overall structure** (blocks, order, intro) is defined by the site's skill,
which takes precedence over this reminder.

## 8. Outline structure (pointer)

**Building the outline** (PAA→sections mapping, proof placement, competitive
gap) and the **heading hierarchy invariants** (≥ 3 H2s, no orphan H2/H3,
2-4 H3s per H2 beyond 150 words, `?` on interrogative headings)
live in the dedicated **`seo-outline`** skill, invoked at step 2bis of `/refresh`
before generation. This skill carries the *substance* of each section; `seo-outline`
carries their *arrangement*.
