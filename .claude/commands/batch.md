---
description: Batch refresh from Google Sheets (all URLs of a given action for a blog).
argument-hint: --action <PARTIAL_REFRESH|FULL_REFRESH|REFRESH_TITLES> --site <site-slug> [--limit N]
allowed-tools: Bash(python3 content_writer.py batch refresh:*), Bash(python3 content_writer.py plan init:*), Bash(python3 content_writer.py plan check:*), Bash(python3 content_writer.py finalize:*), Task, Read, Write, WebSearch, WebFetch, Skill
---

Runs a batch refresh. `--spreadsheet-id` is taken from `.env` if absent.

> 🚫 **Non-negotiable rule - blacklist BEFORE any web fetch.** Read
> `.claude/skills/source-research/references/blacklisted-domains.md` **once at the
> start of the batch**, before the first WebFetch/WebSearch, then **re-check at the
> start of each article** in the loop (re-read or re-summarise the list): the
> constraint must never leave working memory between two iterations. A blacklisted
> domain is never fetched nor kept as a source. Exceptions (Golden Rule, review
> article whose subject IS the platform): see the blacklist file.

## Step 1 - Serial preparation (`cw` CLI)

```bash
python3 content_writer.py batch refresh $ARGUMENTS
```

`cw batch refresh` reads the URLs to process from the **Google Sheet** (the blog's
rows whose action matches), then prepares the context for each one: **fetching the
article's `post_content` from WordPress via the REST API** (`WordPressAPIClient`,
when `wp_api_config` is present; fallback to scraping the public page only when
the REST API is blocked) → GSC/SERP/PAA/intent audit → strategy decision →
`generation_prompt.txt`. This is step 1 of `/refresh`, run serially. For each
URL, note: `context_dir`, `Strategy`, `Keyword` (main keyword), `YTG guide`,
`Assets avant` (assets before), the `Output HTML`/`Output JSON` paths (and
`Type: avis|versus` for enseigna).

URLs in `NO_ACTION`, `BLOCKED_QUALITY_ISSUES`, `ERROR` or
`REDIRECT_301_SUGGESTED` drop out of the batch: report them, nothing to generate.

## Step 2 - Per-article loop (same as /refresh, steps 2 → 4)

The rest is **not** batchable: run the full chain **article by article**, in the
main session for the deterministic steps, via the **content-generator** subagent
(Max subscription, never the paid API) for the writing. For each prepared URL:

1. **Sources (E-E-A-T brief)** - invoke the **`source-research`** skill on the
   topic/URL. Without this brief, `eeat_sources` would be invented by the LLM.

2. **Optimised SEO outline (mandatory, as in /refresh step 2bis)**:

   ```bash
   python3 content_writer.py plan init <url> --site <site-slug>
   ```

   then invoke the **`seo-outline`** skill to fill in `content_plan.md`
   (PAA→sections mapping, proof placement, top 10 gap), and validate:

   ```bash
   python3 content_writer.py plan check <url> --site <site-slug>
   ```

   `OK` → generate; `NEEDS_FIX` → fix the plan then rerun `plan check`.
   **Never** generate on an unvalidated plan - in batch even more than for a
   single URL, this is the safeguard before burning writing tokens.

3. **Generation** - **content-generator** subagent via Task, with
   `generation_prompt.txt`, the validated `content_plan.md`, the sources brief,
   the `site_slug`, the output paths, the `Strategy` and the assets-before count
   (Golden Rule: assets after ≥ before). The subagent writes the files,
   never HTML in the chat.

4. **Finalisation + YTG semantic QC (SOSEO/DSEO)**:

   ```bash
   python3 content_writer.py finalize <url> --site <site-slug> --html-file <Output HTML> [--type <avis|versus>] [--main-keyword "<keyword>"] [--guide-id <YTG guide>]
   ```

   Carry over the `Keyword` and `YTG guide` from step 1 into
   `--main-keyword`/`--guide-id`: the QC then scores SOSEO/DSEO against the right
   guide and reuses the guide instead of recreating it. The target is **not
   uniform**: it depends on the SERP of **each query**. Rule (YTG guide averages,
   `top3_soseo`/`top3_dseo` and `top10_soseo`/`top10_dseo`, retrieved at
   STEP 2.5 of step 1): **article SOSEO > TOP 3 and TOP 10 averages**;
   **DSEO strictly < TOP 3 and TOP 10 averages**. Verdict:
   - `OPTIMAL` → article done, internal linking applied;
   - `NEEDS_FIX` → relaunch the subagent with the under/over-optimised terms,
     then re-run `finalize` (cap of 2-3 iterations);
   - `BLOCKED` → stop **this article** + human alert, move on to the next one.

Do not parallelise generation: finish one article (finalize + YTG verdict)
before moving to the next.

## Step 3 - Batch report

Report: number of URLs processed / discarded (and why), strategy per URL,
`plan check` verdict, YTG verdict with SOSEO/DSEO scores vs target, assets
verdict (before/after), and output paths (`sites/<site-slug>/outputs/`).
