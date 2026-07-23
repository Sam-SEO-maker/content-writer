---
description: YTG semantic QC of an article (URL) - creates/resolves the guide on the main keyword and analyses the content.
argument-hint: <url> ["<main keyword>"] [--fix] [--json-out]
allowed-tools: Bash(python3 content_writer.py ytg qc:*), Read
---

Runs the **YourTextGuru semantic QC** on **one specific article**, designated by its URL.
The analysed content is the **locally generated HTML** (`*.gutenberg.html`) - this is a QC
**before WP publication**, not a scrape of the live page (the Superprof WAF blocks live access).

`$ARGUMENTS` = **`<url>` required**, followed by an **optional main keyword** (in
quotes if it contains spaces). The keyword drives the **creation/resolution of the YTG
guide**: providing it guarantees the right guide. **Provide it as soon as you know it** -
without it, the resolver often falls back to the slug (article title ≠ real SEO keyword →
wrong guide).

From the URL, derive:

1. **`--site`** from the URL's domain / path:
   - `superprof.fr/ressources/...` → `superprof.fr-ressources`
   - `enseigna.fr/...` → `enseigna.fr`
   - (other sites: see `_shared/config/sites.json`)
2. **`--slug`** = last path segment, without extension or trailing slash
   (e.g. `.../francais-terminale/long-bec-fable.html` → `long-bec-fable`).
3. **`--main-keyword`** = the main keyword if provided in `$ARGUMENTS` (overrides the resolver).

Then run:

```bash
python3 content_writer.py ytg qc --site <site_slug> --slug <slug> [--main-keyword "<keyword>"]
```

Add `--fix` (flag the NEEDS_FIX items to the corrector) or `--json-out`
(report `sites/{site-slug}/outputs/ytg_qc_report.json`) if present in `$ARGUMENTS`.
`--main-keyword` requires `--slug` (a single article) - the CLI refuses otherwise.

The engine resolves the main keyword (Notion/Sheet/GSC/slug), resolves or creates the YTG
guide, analyses the HTML → SOSEO/DSEO vs the **TOP 3 / TOP 10 averages of the query's
SERP** (target varies per query: SOSEO > averages, DSEO strictly <
averages - never a uniform threshold), and returns a verdict
**OPTIMAL / NEEDS_FIX / BLOCKED / SKIP**.

If no local `*.gutenberg.html` matches the slug → report it (nothing to analyse:
the article has not been generated locally yet). For the QC of **all** the articles of a
blog, use `python3 content_writer.py ytg qc --site <site-slug>` without `--slug`.

Report a compact summary: verdict, SOSEO/DSEO vs target, and the under/over-optimised terms.
