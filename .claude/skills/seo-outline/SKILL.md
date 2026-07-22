---
name: seo-outline
description: >-
  How to build a good SEO/GEO-optimised editorial outline (all sites), BEFORE
  writing. Turns the data-driven signals (PAA, user intent, top 10 SERP,
  keyword, sources brief) into a traceable H2/H3 outline (content_plan.md):
  question coverage, proof placement, competitive gap, healthy heading
  hierarchy (at least 3 H2s, no orphans, 2-4 H3s per H2, `?` on questions).
  Invoked at step 2bis of /refresh, before generation. Complements
  edito-refresh (substance) and format-wordpress (form).
disable-model-invocation: false
---

# Building a good SEO plan (editorial outline)

A **method** skill: how to go from the collected signals (PAA, intent, SERP,
keyword, sources) to a **traceable outline**, the `content_plan.md` of step 2bis
of `/refresh`, *before* burning writing tokens.

Why an outline separate from the writing:

- **Verifiable**: question coverage, source placement and heading structure
  can be checked on one page, not across 2000 words.
- **Cheap to fix**: if the outline is bad, you fix the outline
  (a few lines), not the whole re-generated article (costly YTG QC
  NEEDS_FIX loop).

> **Boundary with the other skills.** The *substance* (direct answer, density,
> sources, GEO) = `edito-refresh`. The *form* (tags, clean HTML, no links
> in headings) = `format-wordpress`. The *overall structure*
> (blocks, order, intro/FAQ) = the site's skill, which **takes precedence**. This
> skill redefines none of that: it organises the outline.

## Where to write: the skeleton is laid down by `plan init`

Do not guess the path: first run `python3 content_writer.py plan init <url>
--site <site-slug>`. The CLI creates `content_plan.md` in the right `context_dir`,
pre-filled with a template plus the signals (PAA, keyword, intent, assets) extracted
from `audit_data.json` as comments. This skill **fills in** that skeleton; the CLI
writes no prose. Once filled, `plan check` validates it (verdict OK / NEEDS_FIX).

## Inputs

- The **`content_plan.md` skeleton** laid down by `plan init` (path + signals ready).
- `generation_prompt.txt`: PAA, user intent + dominant format, top 10 SERP,
  main + secondary keywords (already collected by `cw refresh`).
- The **verified sources brief** (`source-research`): source → claim → url → year.
- `Assets before`: counts of images/tables/videos/links to preserve (Golden Rule).

## Output: `content_plan.md`

One section per block, each traceable to a signal:

1. **H2/H3 outline**: one line per section, with alongside it:
   - the **PAA(s) covered** (each PAA must appear at least once),
   - the **intent** served (informational / comparative / transactional),
   - the **angle** (what the section brings).
2. **Proof placement**: where the **3 or more institutional sources** and the
   **2 or more statistics** from the brief go, attached to a specific H2 (never "somewhere").
3. **Competitive gap**: angles present in the **top 10 SERP** but missing from
   the article (to add); own differentiating angles to preserve.
4. **Assets**: existing assets to **preserve** (Golden Rule) + assets to **add**,
   per section.

## Method (order of construction)

1. **Anchor the intent**: the SERP's dominant format dictates the skeleton
   ("how-to" guide, comparison, definition...). Do not slap on a generic plan.
2. **Map the PAAs onto sections**: each PAA question → an H2 or H3 that answers
   it up front (direct answer, see `edito-refresh`). Group related PAAs
   under a single H2. No orphan (uncovered) PAA.
3. **Fill the gap**: compare against the top 10's angles; add the missing
   sections that explain their ranking, without copying: bring the extra angle.
4. **Distribute the proofs**: spread sources and stats across several H2s (not
   all in the intro). Every strong claim backed by a source from the brief.
5. **Clean up the hierarchy**: apply the invariants below.
6. **Place the assets**: attach each asset to preserve/add to a section.

## Heading hierarchy invariants (always true)

The site's skill may **tighten** these bounds, never loosen them.

- **At least 3 H2s** per article. Below that, the topic is under-structured for AI extraction.
- **No orphan H2**: every H2 carries content (never two H2s back to back, nor an
  empty H2 serving as a mere transition).
- **No orphan H3**: under an H2, either **0 H3s** or **2 or more H3s**. A single H3
  gets merged into the body of the H2.
- **Subdivision threshold**: if an H2's planned content exceeds **150 words** of
  paragraphs, split it into **2 to 4 H3s**. Below 150 words, no H3.
- **Ceiling**: **max 4 H3s per H2**; beyond that, split the H2 into two separate H2s
  (each in turn respecting the 2-4 H3 rule).
- **Interrogative heading → `?`**: any H2/H3 phrased as a question ends with a
  question mark (French example: « Comment réviser le bac ? »); a declarative
  heading takes none.
- **Correct ATX syntax, never an empty heading**: an H2 is written `## Title`, the
  leading `#` followed by a **space** then the text. `##Title` with no
  space is NOT a heading for markdown: it would come out as plain text in
  WordPress. And a `## ` with no text produces an empty `<h2></h2>` that breaks the
  Gutenberg editor: every `##`/`###` carries a real title, no placeholder left bare.
- `format-wordpress` reminder: **no links** in H2/H3 headings.

> Edge cases of subdivision (H2 at the 150-word limit, multiple PAAs under
> one H2, choosing 3 vs 4 H3s): `references/outline-heuristics.md`.

## Checklist before moving on to generation

- [ ] At least 3 H2s, no orphan H2 or H3, at most 4 H3s per H2.
- [ ] Every collected PAA is covered by at least one section.
- [ ] 3 or more institutional sources and 2 or more stats placed on specific H2s.
- [ ] Top 10 gap filled (missing sections added).
- [ ] All assets to preserve attached to a section (Golden Rule).
- [ ] Interrogative headings punctuated with `?`.

The validated outline is handed to the `content-generator` subagent, which writes
**section by section from it** without reorganising the structure.
