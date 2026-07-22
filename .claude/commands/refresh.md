---
description: Full SEO refresh of a URL (WP REST fetch/scrape → GSC/SERP/PAA/intent → decision → source research → generation via subagent).
argument-hint: <url> --site <enseigna.fr|superprof.fr-ressources> [--strategy X] [--main-keyword K]
allowed-tools: Bash(python3 content_writer.py refresh:*), Bash(python3 content_writer.py finalize:*), Task, Read, Write, WebSearch, WebFetch, Skill
---

Runs the refresh of the given URL by sequencing the workflow chain:
content fetch → GSC → SERP/PAA → user intent → decision →
**source research** → generation → (YTG QC / internal linking in Phase 3bis).

> 🚫 **Non-negotiable rule - blacklist BEFORE any web fetch.** Read
> `.claude/skills/source-research/references/blacklisted-domains.md` **before the
> first WebFetch/WebSearch** of the session (SERP results included). A blacklisted
> domain is never fetched, never kept in a top N, never cited - filtering happens
> a priori, not after curation. Exceptions (existing links = Golden Rule, review
> article whose subject IS the platform): see the blacklist file.

## Step 1 - Deterministic fetch + audit + decision (`cw` CLI)

Run:

```bash
python3 content_writer.py refresh $ARGUMENTS
```

⚠️ **This command already covers steps 1 to 6 of the workflow** (via `_fetch_html`
+ `AuditEngine.full_audit` + `process_url`); do NOT redo them by hand:

- **`post_content` fetch** with 2 automatic strategies (`_fetch_html`):
  1. **WordPress REST API** (`WordPressAPIClient`, when `wp_api_config` is present
     for the blog),
  2. **Scraping fallback** on the public page (`ContentExtractor`) when the REST
     API is blocked.
- **GSC SEO performance** (clicks/impressions/CTR/position, `GSCAnalyzer`, 12-month
  keyword fallback),
- **Main keyword resolution** (GSC → multi-source `KeywordResolver`),
- **SERP analysis**: PAA, features, TOP competitors (`SERPAnalyzer`),
- **User intent** + dominant format (`IntentDetector`),
- **Strategy decision** (data-driven engine) + **prompt composition**.

Output in the displayed `context_dir`:

- `generation_prompt.txt` (composed prompt: strategy + site, GSC/SERP/PAA/intent
  signals already integrated),
- `Output HTML` / `Output JSON` paths, `Strategy`, assets-before count.

If the action is `NO_ACTION`, `BLOCKED_QUALITY_ISSUES`, `ERROR` or
`REDIRECT_301_SUGGESTED`: **stop** and report, nothing to generate.

## Step 2 - Source research (E-E-A-T brief) - the missing piece

`cw refresh` does **not** look for sources: without this step, `eeat_sources`
would be invented by the LLM. Before generating, invoke the **source-research**
skill on the topic/URL (cascade: curated per-subject library if available → web
complement `WebSearch`/`WebFetch` / `deep-research`). Produce a structured brief
(source → claim → url → year), never fabricating a figure.

> As long as `sites/<site-slug>/sources/` does not exist (Phase 4), the skill
> operates in web-only mode.

## Step 2bis - Optimised editorial outline (verifiable artefact)

Before generating, produce a **traceable outline** in `content_plan.md`. Goal:
verify coverage **before** burning writing tokens, and make the fix (if the
outline is bad) a hundred times cheaper than a re-generation.

**Deterministic scaffold** - first lay the skeleton at the right path, with the
signals (PAA, keyword, intent, assets) injected from `audit_data.json`:

```bash
python3 content_writer.py plan init <url> --site <site-slug>
```

Then invoke the **`seo-outline`** skill to **fill in** this outline
(PAA→sections mapping, proof placement, top 10 gap) from the signals in
`generation_prompt.txt` + the sources brief. The CLI laid the structure; the agent
writes the H2s/H3s.

The `seo-outline` skill carries the detail (PAA→sections mapping, proof placement,
competitive gap, heading invariants: ≥ 3 H2s, no orphan H2/H3, 2-4 H3s per
H2 beyond 150 words, `?` on interrogative headings).

Once `content_plan.md` is written, **validate it mechanically** (deterministic,
zero tokens) before generating:

```bash
python3 content_writer.py plan check <url> --site <site-slug>
```

- **OK** → move on to step 3;
- **NEEDS_FIX** → fix the plan according to the listed shortcomings (cheap), then
  rerun `plan check`. Do **not** generate on an `NEEDS_FIX` plan.

The validated `content_plan.md` is an **additional input** passed to the subagent
at step 3: it writes *from the outline*, it does not reinvent it.

## Step 3 - Generation (`content-generator` subagent)

Delegate the writing to the **content-generator** subagent (Max subscription,
never the paid API) via the Task tool. Pass it:

- the `generation_prompt.txt` path (already contains PAA, intent, SERP, keyword),
- **the `content_plan.md` from step 2bis** (validated outline: the subagent writes
  from this plan, section by section),
- **the verified sources brief from step 2** (to inject into the content and
  into `eeat_sources`, no invention),
- the `site_slug` (to load the right writing skill),
- the `Output HTML` / `Output JSON` paths,
- the `Strategy` and the assets-before count (Golden Rule: assets after ≥ before).

The subagent writes the raw HTML + metadata directly to the output files; it
**does not return** HTML in the chat. Note the path of the written raw HTML
(`Output HTML`), it is required at step 4.

## Step 4 - Deterministic finalisation (`cw finalize`)

Once the raw HTML is written, chain save → assets → YTG QC → internal linking:

```bash
python3 content_writer.py finalize <url> --site <site-slug> --html-file <Output HTML> [--type <avis|versus>] [--main-keyword "<keyword>"] [--guide-id <YTG guide>]
```

> **Keyword + YTG guide.** Step 1 (`cw refresh`) prints `Keyword:` (main keyword)
> and `YTG guide:` when STEP 2.5 created a guide. **Carry both over** into
> `--main-keyword`/`--guide-id`: the post-generation QC then scores against the
> right guide (the real keyword, not the slug) and **reuses** the guide instead of
> recreating it (credit savings). If absent → the QC re-resolves the keyword
> (slug fallback).

> **Article type (enseigna).** Step 6 of the `refresh` CLI prints a
> `Type: avis|versus` line when the URL is classified (rule: slug `superprof-vs-*` →
> versus; slug containing `avis` → avis; otherwise nothing). If a `Type:` is
> printed, **carry it over as-is into `--type`**: the HTML output is then routed
> into `sites/enseigna/outputs/html/{type}/` and the versus prompt
> (`vs_concurrent.md`) is already injected at generation. Without `Type:`, do not
> pass `--type`.

This (deterministic) command:

- **saves** the bare HTML + `.gutenberg.html` + table CSVs,
- **validates the assets** (Golden Rule; restores missing ones),
- runs the **YTG semantic QC** → verdict:
  - `OPTIMAL` → proceeds with internal linking,
  - `NEEDS_FIX` → returns the under/over-optimised terms: **relaunch the
    content-generator subagent** to fix the HTML (loop, cap of 2-3 iterations),
    then rerun `finalize`,
  - `BLOCKED` → **stop + human alert** (severe over-optimisation, no linking,
    no automatic re-generation),
- applies the **internal linking** (`EnseignaAvisLinker` for enseigna; for
  superprof the landing links are injected upstream by `SuperprofRotator`). Add
  `--apply-linking` to write the links (otherwise dry-run).

## Step 5 - Report

Report: applied strategy, selected sources, output paths
(`sites/<site-slug>/outputs/`), YTG verdict, assets verdict (before/after), and
links added. Goal: URL → content + verdict + links, with no manual rework.
